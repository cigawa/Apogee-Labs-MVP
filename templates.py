"""
Prompt construction for the vibration MVP.

Three LLM jobs:
  1. design_fixture_spec  -> returns STRUCTURED JSON the CAD engine builds from
  2. design_recommendations -> prose: material choice, mounting, resonance strategy
  3. report_narrative -> assembles the automated test report from all artifacts

The fixture-spec prompt is constrained to emit ONLY valid JSON matching the
FixtureSpec schema, so geometry generation stays deterministic and reviewable.
"""

import json

# --------------------------------------------------------------------------- #
# 1. Fixture spec (JSON-only)
# --------------------------------------------------------------------------- #
FIXTURE_SPEC_SYSTEM = """\
You are an expert spacecraft vibration test engineer designing a custom test \
FIXTURE that mounts a test article to an electrodynamic shaker / slip table. \
You output ONLY a JSON object matching the schema below (no prose, no code \
fences). The fixture must: be stiff (first fixture mode well above the test \
band, ideally >2000 Hz), provide a flat bolt interface to both the shaker table \
and the test article, and avoid introducing its own resonances into the test.

Design heuristics:
- Base plate footprint should exceed the test article footprint with margin for \
the table bolt pattern.
- Thicker base plate + ribs raise fixture stiffness/first mode. Aluminum \
(6061-T6 or 7075-T6) is standard for the high stiffness-to-mass ratio.
- Table bolt pattern: 4 holes near the plate corners sized for the shaker insert \
(M8 -> 9 mm clearance is typical). Article bolt pattern: matches the test \
article's mounting feet.
- Keep fixture mass reasonable relative to shaker force capacity.

JSON schema (units mm; include every key):
{
  "base_length_mm": number, "base_width_mm": number, "base_thickness_mm": number,
  "table_bolt_pattern": {"spacing_x_mm": number, "spacing_y_mm": number, "hole_dia_mm": number},
  "boss_length_mm": number, "boss_width_mm": number, "boss_height_mm": number,
  "article_bolt_pattern": {"spacing_x_mm": number, "spacing_y_mm": number, "hole_dia_mm": number},
  "edge_chamfer_mm": number, "add_ribs": boolean, "rib_thickness_mm": number,
  "material": string,
  "rationale": string   // 2-4 sentences explaining the key design choices
}
Output ONLY the JSON object."""


def build_fixture_spec_prompt(inputs: dict, user_prompt: str,
                              extracted: dict | None = None) -> str:
    blocks = ["TEST ARTICLE & MISSION INPUTS:"]
    for k, v in inputs.items():
        if v not in (None, "", "Not specified"):
            blocks.append(f"- {k.replace('_',' ').title()}: {v}")
    if extracted:
        blocks.append("\nPARAMETERS EXTRACTED FROM UPLOADED DOCUMENTS:")
        blocks.append(json.dumps(extracted, indent=2))
    if user_prompt:
        blocks.append(f"\nTEST ENGINEER REQUEST:\n{user_prompt}")
    blocks.append("\nProduce the fixture spec JSON now.")
    return "\n".join(blocks)


# --------------------------------------------------------------------------- #
# 2. Design recommendations (prose, grounded in retrieved standards)
# --------------------------------------------------------------------------- #
RECOMMENDATIONS_SYSTEM = """\
You are an expert spacecraft vibration test engineer. Using the provided \
standards excerpts and the fixture design, write concise design \
recommendations covering: (1) material and stiffness rationale, (2) mounting / \
bolt-interface and load-path considerations, (3) resonance-avoidance and \
accelerometer placement, (4) any reliability risks to flag. Cite the governing \
standard by name where relevant. Be specific and technical but concise. End by \
clearly stating this is a draft requiring test engineer review."""


def build_recommendations_prompt(inputs: dict, fixture_spec: dict,
                                 retrieved_chunks) -> str:
    excerpts = "\n\n".join(
        f"[{c.source} | {c.topic}]\n{c.text}" for c in retrieved_chunks
    )
    return f"""\
TEST ARTICLE & MISSION INPUTS:
{json.dumps(inputs, indent=2)}

PROPOSED FIXTURE SPEC:
{json.dumps(fixture_spec, indent=2)}

STANDARDS EXCERPTS (authoritative):
{excerpts}

Write the design recommendations now."""


# --------------------------------------------------------------------------- #
# 3. Automated test report narrative
# --------------------------------------------------------------------------- #
REPORT_SYSTEM = """\
You are generating a DRAFT vibration test report for test engineer review. \
Use ONLY the provided artifacts (inputs, fixture spec, computed vibration \
profile, recommendations). Structure the report with these sections:
## 1. Test Overview
## 2. Test Article & Configuration
## 3. Fixture Design Summary
## 4. Random Vibration Test Profile  (state the breakpoints, Grms, duration, level)
## 5. Notching & Overtesting Mitigation
## 6. Test Sequence / Procedure Steps  (numbered, for engineers & technicians)
## 7. Pass / Fail Criteria
## 8. Items Requiring Test Engineer Review
Be precise. Do not invent numbers beyond those provided. Cite standards by name.
State clearly that this is an AI-generated draft requiring qualified review."""


def build_report_prompt(inputs: dict, fixture_spec: dict, profile: dict,
                        recommendations: str, retrieved_chunks) -> str:
    excerpts = "\n\n".join(
        f"[{c.source} | {c.topic}]\n{c.text}" for c in retrieved_chunks
    )
    return f"""\
INPUTS:
{json.dumps(inputs, indent=2)}

FIXTURE SPEC:
{json.dumps(fixture_spec, indent=2)}

COMPUTED VIBRATION PROFILE:
{json.dumps(profile, indent=2)}

DESIGN RECOMMENDATIONS (already drafted):
{recommendations}

STANDARDS EXCERPTS:
{excerpts}

Generate the draft test report now."""
