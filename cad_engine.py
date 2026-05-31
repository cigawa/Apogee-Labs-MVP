"""
Parametric vibration test fixture CAD engine (CadQuery).

Design philosophy: the LLM does not emit raw CAD code. Instead it emits a
STRUCTURED FIXTURE SPEC (a validated dict / JSON). This engine deterministically
turns that spec into real geometry and exports STEP, STL, and an SVG preview.
That keeps geometry generation reliable and reviewable, and the spec itself is a
clean artifact for test engineers and for the RLHF feedback loop.

A typical vibration fixture (for mounting a test article to a shaker/slip table):
  - a base plate that bolts to the shaker head expander / slip table grid
  - a raised interface/boss pattern that the test article bolts onto
  - through-holes for both bolt patterns
Optional: stiffening ribs, a cavity to reduce mass, chamfered edges.

If CadQuery is unavailable (e.g. won't compile on Windows ARM), import of this
module fails gracefully and the app degrades to spec-only mode.
"""

from dataclasses import dataclass, field, asdict
from typing import List, Optional, Tuple
import os

try:
    import cadquery as cq
    from cadquery import exporters
    CADQUERY_AVAILABLE = True
    CADQUERY_IMPORT_ERROR = None
except Exception as e:  # noqa: BLE001
    CADQUERY_AVAILABLE = False
    CADQUERY_IMPORT_ERROR = str(e)


# --------------------------------------------------------------------------- #
# Structured fixture specification
# --------------------------------------------------------------------------- #
@dataclass
class BoltPattern:
    """A rectangular bolt-hole pattern (4 corners)."""
    spacing_x_mm: float
    spacing_y_mm: float
    hole_dia_mm: float


@dataclass
class FixtureSpec:
    """Everything needed to build a parametric fixture. Units: mm."""
    # Base plate (bolts to shaker table)
    base_length_mm: float = 200.0
    base_width_mm: float = 200.0
    base_thickness_mm: float = 15.0
    table_bolt_pattern: BoltPattern = field(
        default_factory=lambda: BoltPattern(160, 160, 9.0)
    )
    # Raised interface boss (test article mounts here)
    boss_length_mm: float = 100.0
    boss_width_mm: float = 100.0
    boss_height_mm: float = 25.0
    article_bolt_pattern: BoltPattern = field(
        default_factory=lambda: BoltPattern(80, 80, 5.5)
    )
    # Options
    edge_chamfer_mm: float = 3.0
    add_ribs: bool = True
    rib_thickness_mm: float = 8.0
    material: str = "6061-T6 Aluminum"
    # Free-text design rationale from the LLM (for the report + review)
    rationale: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        return d

    def estimated_mass_kg(self) -> float:
        """Rough solid-volume mass estimate (ignores holes/cavities)."""
        # density kg/mm^3 for common materials
        density = {
            "6061-T6 Aluminum": 2.70e-6,
            "7075-T6 Aluminum": 2.81e-6,
            "Steel": 7.85e-6,
            "Stainless Steel": 8.00e-6,
            "Magnesium": 1.74e-6,
        }.get(self.material, 2.70e-6)
        base_v = self.base_length_mm * self.base_width_mm * self.base_thickness_mm
        boss_v = self.boss_length_mm * self.boss_width_mm * self.boss_height_mm
        return round((base_v + boss_v) * density, 3)


# --------------------------------------------------------------------------- #
# Geometry builder
# --------------------------------------------------------------------------- #
def build_fixture(spec: FixtureSpec):
    """Return a CadQuery Workplane solid for the given spec."""
    if not CADQUERY_AVAILABLE:
        raise RuntimeError(
            f"CadQuery not available: {CADQUERY_IMPORT_ERROR}"
        )

    # Base plate
    fixture = (
        cq.Workplane("XY")
        .box(spec.base_length_mm, spec.base_width_mm, spec.base_thickness_mm)
    )

    # Table bolt holes (through the base plate)
    tbp = spec.table_bolt_pattern
    fixture = (
        fixture.faces(">Z").workplane()
        .rect(tbp.spacing_x_mm, tbp.spacing_y_mm, forConstruction=True)
        .vertices()
        .hole(tbp.hole_dia_mm)
    )

    # Raised interface boss, centered on top of the base plate
    boss = (
        cq.Workplane("XY")
        .workplane(offset=spec.base_thickness_mm / 2.0)
        .box(spec.boss_length_mm, spec.boss_width_mm, spec.boss_height_mm,
             centered=(True, True, False))
    )
    fixture = fixture.union(boss)

    # Article bolt holes (into the top of the boss)
    abp = spec.article_bolt_pattern
    top_z = spec.base_thickness_mm / 2.0 + spec.boss_height_mm
    fixture = (
        fixture.faces(">Z").workplane()
        .rect(abp.spacing_x_mm, abp.spacing_y_mm, forConstruction=True)
        .vertices()
        .hole(abp.hole_dia_mm, depth=spec.boss_height_mm * 0.8)
    )

    # Optional stiffening ribs (two crossing ribs under the boss footprint)
    if spec.add_ribs:
        try:
            rib_h = spec.boss_height_mm
            rib_x = (
                cq.Workplane("XY").workplane(offset=spec.base_thickness_mm / 2.0)
                .box(spec.base_length_mm * 0.9, spec.rib_thickness_mm, rib_h,
                     centered=(True, True, False))
            )
            rib_y = (
                cq.Workplane("XY").workplane(offset=spec.base_thickness_mm / 2.0)
                .box(spec.rib_thickness_mm, spec.base_width_mm * 0.9, rib_h,
                     centered=(True, True, False))
            )
            fixture = fixture.union(rib_x).union(rib_y).union(boss)
            # re-cut article holes after rib union (union can cover them)
            fixture = (
                fixture.faces(">Z").workplane()
                .rect(abp.spacing_x_mm, abp.spacing_y_mm, forConstruction=True)
                .vertices()
                .hole(abp.hole_dia_mm, depth=spec.boss_height_mm * 0.8)
            )
        except Exception:
            pass  # ribs are a nicety; never fail the whole build over them

    # Chamfer the outer top edges of the base plate for a finished look
    if spec.edge_chamfer_mm and spec.edge_chamfer_mm > 0:
        try:
            fixture = fixture.edges("|Z").chamfer(spec.edge_chamfer_mm)
        except Exception:
            pass

    return fixture


def export_fixture(spec: FixtureSpec, out_dir: str, basename: str = "fixture"
                   ) -> dict:
    """
    Build and export the fixture. Returns paths dict:
      {"step": ..., "stl": ..., "svg": ..., "mass_kg": ...}
    """
    os.makedirs(out_dir, exist_ok=True)
    fixture = build_fixture(spec)

    paths = {}
    step_path = os.path.join(out_dir, f"{basename}.step")
    stl_path = os.path.join(out_dir, f"{basename}.stl")
    svg_path = os.path.join(out_dir, f"{basename}.svg")

    exporters.export(fixture, step_path)
    exporters.export(fixture, stl_path)
    exporters.export(
        fixture, svg_path,
        opt={"width": 520, "height": 380, "showAxes": False,
             "projectionDir": (1, 1, 1), "strokeWidth": 0.5},
    )

    paths["step"] = step_path
    paths["stl"] = stl_path
    paths["svg"] = svg_path
    paths["mass_kg"] = spec.estimated_mass_kg()
    return paths
