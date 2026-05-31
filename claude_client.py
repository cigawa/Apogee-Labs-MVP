"""
Claude client for the vibration MVP.

Provides:
  - generate_fixture_spec(): returns a validated FixtureSpec (mock fallback)
  - generate_prose(): generic prose call for recommendations & report

Without ANTHROPIC_API_KEY everything still runs using a deterministic fallback
fixture spec and clearly-labeled mock prose, so the CAD + profile demo works
end-to-end offline.
"""

import json
import os
from typing import Optional

from cad_engine import FixtureSpec, BoltPattern

DEFAULT_MODEL = "claude-opus-4-20250514"


# --------------------------------------------------------------------------- #
def _fallback_spec(inputs: dict) -> FixtureSpec:
    """Deterministic, reasonable fixture when no LLM is available."""
    # crude sizing from mass if provided
    spec = FixtureSpec()
    spec.rationale = (
        "[MOCK fixture — no API key] Default 200x200x15 mm 6061-T6 base with a "
        "100x100x25 mm raised boss, corner table bolts and a centered article "
        "bolt pattern, ribs added for stiffness. Set ANTHROPIC_API_KEY for an "
        "AI-tailored design."
    )
    return spec


def _coerce_spec(d: dict) -> FixtureSpec:
    """Validate/parse an LLM JSON dict into a FixtureSpec, with safe defaults."""
    def num(x, default):
        try:
            return float(x)
        except (TypeError, ValueError):
            return default

    tbp = d.get("table_bolt_pattern", {}) or {}
    abp = d.get("article_bolt_pattern", {}) or {}
    spec = FixtureSpec(
        base_length_mm=num(d.get("base_length_mm"), 200),
        base_width_mm=num(d.get("base_width_mm"), 200),
        base_thickness_mm=num(d.get("base_thickness_mm"), 15),
        table_bolt_pattern=BoltPattern(
            num(tbp.get("spacing_x_mm"), 160),
            num(tbp.get("spacing_y_mm"), 160),
            num(tbp.get("hole_dia_mm"), 9),
        ),
        boss_length_mm=num(d.get("boss_length_mm"), 100),
        boss_width_mm=num(d.get("boss_width_mm"), 100),
        boss_height_mm=num(d.get("boss_height_mm"), 25),
        article_bolt_pattern=BoltPattern(
            num(abp.get("spacing_x_mm"), 80),
            num(abp.get("spacing_y_mm"), 80),
            num(abp.get("hole_dia_mm"), 5.5),
        ),
        edge_chamfer_mm=num(d.get("edge_chamfer_mm"), 3),
        add_ribs=bool(d.get("add_ribs", True)),
        rib_thickness_mm=num(d.get("rib_thickness_mm"), 8),
        material=str(d.get("material", "6061-T6 Aluminum")),
        rationale=str(d.get("rationale", "")),
    )
    return spec


def generate_fixture_spec(system_prompt: str, user_prompt: str,
                          inputs: dict, model: str = DEFAULT_MODEL) -> dict:
    """
    Returns {"spec": FixtureSpec, "mode": "live"|"mock"|"error", "raw": str}.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return {"spec": _fallback_spec(inputs), "mode": "mock", "raw": ""}

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model=model, max_tokens=1200,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        raw = "".join(b.text for b in msg.content if b.type == "text").strip()
        cleaned = raw.replace("```json", "").replace("```", "").strip()
        spec = _coerce_spec(json.loads(cleaned))
        return {"spec": spec, "mode": "live", "raw": raw}
    except Exception as e:  # noqa: BLE001
        fb = _fallback_spec(inputs)
        fb.rationale = f"[Spec generation error: {e}] " + fb.rationale
        return {"spec": fb, "mode": "error", "raw": str(e)}


def generate_prose(system_prompt: str, user_prompt: str,
                   label: str = "content",
                   model: str = DEFAULT_MODEL, max_tokens: int = 2500) -> dict:
    """Generic prose generation with mock fallback."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return {"text": f"> **MOCK {label}** — set ANTHROPIC_API_KEY for real "
                        f"AI-generated {label}.", "mode": "mock"}
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model=model, max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        text = "".join(b.text for b in msg.content if b.type == "text")
        return {"text": text, "mode": "live"}
    except Exception as e:  # noqa: BLE001
        return {"text": f"**Error generating {label}:** {e}", "mode": "error"}
