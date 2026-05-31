# Apogee Labs — Vibration Test Automation MVP

> **Flat layout:** every file lives in one folder (no subfolders). This makes
> GitHub browser-upload and Streamlit Cloud deployment painless. On Streamlit
> Cloud, set **Main file path** to `main.py`.

A focused, demonstrable proof-of-concept for **vibration test automation**, built
for seed investor demos and a Phase I STTR application. It takes mission + test
article inputs (and optional uploaded documents) and produces three outputs in
one end-to-end flow:

1. **Custom fixture CAD** — a real, downloadable STEP/STL fixture with an
   isometric preview, designed by Claude and built deterministically by CadQuery.
2. **Random vibration test profile** — a real GEVS-based PSD with computed Grms,
   mass attenuation, and notch suggestions (math, not LLM guesswork).
3. **Automated draft test report** — fixture summary, profile, procedure steps,
   pass/fail criteria, and an explicit "needs engineer review" section.

Plus a **test-engineer feedback loop** that captures edits + ratings as JSONL —
the seed of the proprietary RLHF dataset.

## Architecture (matches the plan; license-and-integrate philosophy)

```
app/main.py              Streamlit UI (uploads, 3 output tabs, feedback form)
prompts/templates.py     LLM prompts: fixture-spec JSON, recommendations, report
engines/cad_engine.py    CadQuery parametric fixture builder (STEP/STL/SVG)
engines/profile_engine.py Deterministic PSD / Grms / notch math (NASA-STD-7001/GEVS)
utils/retriever.py       TF-IDF RAG over standards (swap for LlamaIndex later)
utils/doc_parser.py      Claude-native doc parsing; LlamaParse/Unstructured scaffolded
utils/claude_client.py   Spec generation (validated JSON) + prose, mock fallbacks
utils/feedback.py        RLHF feedback capture (JSONL; swap for SQL later)
corpus/vibration.py      Curated public vibration standards
```

Key design choice: the LLM emits a **structured fixture spec (JSON)**, and the
CAD engine builds geometry from it. Geometry stays deterministic and reviewable;
the spec is also a clean artifact for the feedback loop.

## Setup

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...     # optional; see modes below
streamlit run main.py
```

### Modes without an API key
- **Fixture CAD + vibration profile**: fully live (no key needed).
- **Document parsing + AI design text + report**: mocked until a key is set.

So you can demo the CAD and the real Grms/PSD math offline; add the key for the
full AI narrative.

## ⚠️ Windows ARM note (important for your machine)

`cadquery` has a compiled geometry kernel and **may not install on Windows ARM**
(same wheel issue you hit with pyarrow/httptools). Two clean options:

1. **Recommended — host on Streamlit Community Cloud** (Linux), where cadquery
   installs cleanly *and* you get the shareable demo URL for LOIs/investors.
2. **Local fallback** — comment out the `cadquery` line in `requirements.txt`.
   The app still runs; the CAD tab shows a disabled notice, while the profile,
   report, and feedback features work fully.

## Standards grounding

GEVS GSFC-STD-7000, NASA-STD-7001/7002, NASA-HDBK-7004/7005 (force-limited
vibration / notching), MIL-STD-1540, and launch vehicle user's guides. The
corpus chunks are simplified summaries for the MVP; production ingests full text
via LlamaParse + LlamaIndex.

## Suggested next steps

1. Add a launch-vehicle PSD library so the profile envelopes the real LV
   environment instead of only the workmanship spectrum.
2. Wire LlamaParse for robust parsing of real launch vehicle user's guides.
3. Run the validation study (engineers score outputs; target 60%+); the feedback
   JSONL already captures exactly the data you need to report.
4. Add a Leo AI toggle alongside CadQuery for natural-language CAD.
