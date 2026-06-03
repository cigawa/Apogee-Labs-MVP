"""
Apogee Labs — Vibration Test Automation MVP

End-to-end demo:
  Inputs (form + file uploads + engineer prompt)
    -> [optional] Claude parses uploaded docs
    -> Claude designs a structured fixture spec
    -> CadQuery builds real STEP/STL/SVG geometry
    -> Profile engine computes the random vibration PSD + Grms + notches
    -> Claude writes design recommendations and the draft test report
    -> Engineer edits + rates output (RLHF feedback capture)

Run:
    pip install -r requirements.txt
    export ANTHROPIC_API_KEY=sk-ant-...      # optional; mock without it
    streamlit run app/main.py
"""

import os
import sys
import json
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st
import pandas as pd

from unified_retriever import UnifiedRetriever
from claude_client import generate_fixture_spec, generate_prose
from doc_parser import extract_with_claude
from feedback import save_feedback, feedback_stats
from cad_engine import (export_fixture, CADQUERY_AVAILABLE,
                                 CADQUERY_IMPORT_ERROR)
from profile_engine import compute_profile, profile_as_table
from templates import (
    FIXTURE_SPEC_SYSTEM, build_fixture_spec_prompt,
    RECOMMENDATIONS_SYSTEM, build_recommendations_prompt,
    REPORT_SYSTEM, build_report_prompt,
)

st.set_page_config(
    page_title="Apogee Labs — Vibration Test Automation",
    page_icon="🛰️", 
    layout="wide"
)

# ====================== CUSTOM FUTURISTIC FONT ======================
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Exo+2:wght@400;500;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Exo 2', sans-serif !important;
    }

    h1, h2, h3, h4, h5, h6, .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {
        font-family: 'Exo 2', sans-serif !important;
        font-weight: 600;
    }

    .stButton>button {
        font-family: 'Exo 2', sans-serif;
        font-weight: 600;
    }
    </style>
""", unsafe_allow_html=True)
# ===================================================================

# --- session state ----------------------------------------------------------
for key in ("results", "extracted"):
    st.session_state.setdefault(key, None)

# --- header -----------------------------------------------------------------
st.title("🛰️ Apogee Labs — Vibration Test Automation")
st.caption(
    "MVP: fixture CAD design · random vibration profile · automated test report. "
    "Grounded in public NASA/DoD standards. "
    "**All output is a DRAFT requiring qualified test engineer review.**"
)

key_present = bool(os.environ.get("ANTHROPIC_API_KEY"))
c1, c2 = st.columns(2)
with c1:
    if key_present:
        st.success("Anthropic API key detected — live generation enabled.")
    else:
        st.warning("No ANTHROPIC_API_KEY — fixture/profile run live; "
                   "AI design text & doc parsing are mocked.")
with c2:
    if CADQUERY_AVAILABLE:
        st.success("CadQuery available — real CAD (STEP/STL) generation enabled.")
    else:
        st.error(f"CadQuery unavailable — CAD disabled. ({CADQUERY_IMPORT_ERROR}) "
                 "Run on Streamlit Cloud (Linux) where it installs cleanly.")

# ============================================================================
# 1. INPUTS
# ============================================================================
st.header("1. Inputs")

colA, colB = st.columns(2)
with colA:
    article_name = st.text_input("Test article name", "3U CubeSat")
    mass_kg = st.number_input("Test article mass (kg)", min_value=0.0,
                              value=4.0, step=0.5)
    test_level = st.selectbox("Test level",
                              ["qualification", "protoflight", "acceptance"])
with colB:
    orbit = st.selectbox("Orbit / destination",
                         ["LEO", "SSO", "MEO", "GEO", "Lunar", "Not specified"])
    launch_vehicle = st.selectbox(
        "Launch vehicle",
        ["Falcon 9", "Electron", "Vulcan", "New Glenn", "Not specified / TBD"])
    resonances_str = st.text_input(
        "Known resonant frequencies (Hz, comma-sep) — optional",
        placeholder="e.g. 320, 610")

engineer_prompt = st.text_area(
    "Test engineer request",
    value="Design me a custom aluminum fixture to mount this article to the shaker.",
    height=70)

uploads = st.file_uploader(
    "Upload mission specs / launch vehicle guide / test article datasheet "
    "(PDF or image) — optional",
    type=["pdf", "png", "jpg", "jpeg"], accept_multiple_files=True)

# optional: parse uploads
if uploads and st.button("📄 Parse uploaded documents"):
    if not key_present:
        st.warning("Document parsing needs an API key. Skipping.")
    else:
        merged = {}
        for uf in uploads:
            with tempfile.NamedTemporaryFile(
                    delete=False, suffix=os.path.splitext(uf.name)[1]) as tmp:
                tmp.write(uf.getbuffer())
                tmp_path = tmp.name
            with st.spinner(f"Parsing {uf.name}..."):
                res = extract_with_claude(tmp_path)
            if res["ok"]:
                merged.update({k: v for k, v in res["data"].items() if v})
            else:
                st.error(f"{uf.name}: {res['error']}")
            os.unlink(tmp_path)
        st.session_state.extracted = merged or None
        if merged:
            st.success("Extracted parameters:")
            st.json(merged)

# ============================================================================
# 2. GENERATE
# ============================================================================
st.header("2. Generate")

if st.button("⚙️ Generate Fixture + Profile + Report", type="primary"):
    resonances = []
    for tok in resonances_str.split(","):
        tok = tok.strip()
        if tok:
            try:
                resonances.append(float(tok))
            except ValueError:
                pass

    inputs = {
        "test_article_name": article_name,
        "mass_kg": mass_kg,
        "test_level": test_level,
        "orbit": orbit,
        "launch_vehicle": launch_vehicle,
        "known_resonances_hz": resonances or "Not specified",
    }

    retriever = UnifiedRetriever()
    chunks = retriever.all_chunks()

    with st.spinner("Designing fixture..."):
        spec_prompt = build_fixture_spec_prompt(
            inputs, engineer_prompt, st.session_state.extracted)
        spec_res = generate_fixture_spec(FIXTURE_SPEC_SYSTEM, spec_prompt, inputs)
        spec = spec_res["spec"]

    cad_paths = None
    cad_error = None
    if CADQUERY_AVAILABLE:
        with st.spinner("Building CAD geometry (STEP / STL / preview)..."):
            try:
                out_dir = os.path.join(tempfile.gettempdir(), "apogee_cad")
                cad_paths = export_fixture(spec, out_dir,
                                           f"fixture_{article_name.replace(' ','_')}")
            except Exception as e:  # noqa: BLE001
                cad_error = str(e)

    with st.spinner("Computing vibration profile..."):
        profile = compute_profile(test_level, mass_kg=mass_kg,
                                  resonances_hz=resonances)

    with st.spinner("Writing design recommendations..."):
        rec_prompt = build_recommendations_prompt(inputs, spec.to_dict(), chunks)
        rec = generate_prose(RECOMMENDATIONS_SYSTEM, rec_prompt,
                             label="recommendations")

    with st.spinner("Generating draft test report..."):
        profile_dict = {
            "level": profile.level,
            "duration_s_per_axis": profile.duration_s_per_axis,
            "overall_grms": profile.overall_grms,
            "mass_attenuation_db": profile.mass_attenuation_db,
            "breakpoints": profile_as_table(profile),
            "notches": profile.notches,
            "notes": profile.notes,
        }
        rep_prompt = build_report_prompt(inputs, spec.to_dict(), profile_dict,
                                         rec["text"], chunks)
        report = generate_prose(REPORT_SYSTEM, rep_prompt, label="report",
                               max_tokens=3000)

    st.session_state.results = {
        "inputs": inputs, "spec": spec, "spec_mode": spec_res["mode"],
        "cad_paths": cad_paths, "cad_error": cad_error,
        "profile": profile, "profile_dict": profile_dict,
        "recommendations": rec["text"], "report": report["text"],
    }

# ============================================================================
# 3. RESULTS
# ============================================================================
res = st.session_state.results
if res:
    st.header("3. Results")
    tab1, tab2, tab3 = st.tabs(
        ["🔧 Fixture Design", "📈 Vibration Profile", "📄 Test Report"])

    # ---- Fixture --------------------------------------------------------
    with tab1:
        spec = res["spec"]
        st.subheader("Custom Fixture Design")
        if res["spec_mode"] != "live":
            st.info(f"Fixture spec mode: {res['spec_mode']} "
                    "(set API key for AI-tailored design).")
        lc, rc = st.columns([1, 1])
        with lc:
            if res["cad_paths"] and os.path.exists(res["cad_paths"]["svg"]):
                with open(res["cad_paths"]["svg"], "r", encoding="utf-8") as f:
                    st.image(f.read(), caption="Fixture preview (isometric)")
            elif res["cad_error"]:
                st.error(f"CAD build error: {res['cad_error']}")
            else:
                st.info("CAD preview unavailable in this environment.")
        with rc:
            st.markdown(f"**Material:** {spec.material}")
            st.markdown(f"**Est. mass:** {spec.estimated_mass_kg()} kg")
            st.markdown(f"**Base:** {spec.base_length_mm}×{spec.base_width_mm}"
                        f"×{spec.base_thickness_mm} mm")
            st.markdown(f"**Boss:** {spec.boss_length_mm}×{spec.boss_width_mm}"
                        f"×{spec.boss_height_mm} mm")
            st.markdown(f"**Table bolts:** {spec.table_bolt_pattern.spacing_x_mm}"
                        f"×{spec.table_bolt_pattern.spacing_y_mm} mm, "
                        f"⌀{spec.table_bolt_pattern.hole_dia_mm} mm")
            st.markdown(f"**Article bolts:** {spec.article_bolt_pattern.spacing_x_mm}"
                        f"×{spec.article_bolt_pattern.spacing_y_mm} mm, "
                        f"⌀{spec.article_bolt_pattern.hole_dia_mm} mm")
        if spec.rationale:
            st.markdown(f"**Design rationale:** {spec.rationale}")

        if res["cad_paths"]:
            d1, d2 = st.columns(2)
            with d1:
                with open(res["cad_paths"]["step"], "rb") as f:
                    st.download_button("⬇️ Download STEP", f.read(),
                                       file_name="fixture.step")
            with d2:
                with open(res["cad_paths"]["stl"], "rb") as f:
                    st.download_button("⬇️ Download STL", f.read(),
                                       file_name="fixture.stl")

        st.divider()
        st.markdown("### Design Recommendations")
        st.markdown(res["recommendations"])

    # ---- Profile --------------------------------------------------------
    with tab2:
        profile = res["profile"]
        st.subheader("Random Vibration Test Profile")
        m1, m2, m3 = st.columns(3)
        m1.metric("Overall Grms", profile.overall_grms)
        m2.metric("Duration/axis", f"{profile.duration_s_per_axis} s")
        m3.metric("Mass atten.", f"{profile.mass_attenuation_db} dB")

        df = pd.DataFrame(profile_as_table(profile))
        # log-log PSD plot
        chart_df = df.rename(columns={"Frequency (Hz)": "freq",
                                      "ASD (g^2/Hz)": "asd"}).set_index("freq")
        st.line_chart(chart_df)
        st.caption("PSD breakpoints (GEVS generalized workmanship envelope, "
                   "adjusted for level and mass).")
        st.dataframe(df, use_container_width=True)

        if profile.notches:
            st.markdown("**Suggested notches:**")
            st.dataframe(pd.DataFrame(profile.notches), use_container_width=True)
        for n in profile.notes:
            st.markdown(f"- {n}")

    # ---- Report ---------------------------------------------------------
    with tab3:
        st.subheader("Draft Test Report")
        st.markdown(res["report"])
        st.download_button("⬇️ Download report (Markdown)", res["report"],
                           file_name="vibration_test_report.md",
                           mime="text/markdown")

    # ---- Feedback / RLHF loop ------------------------------------------
    st.divider()
    st.header("4. Test Engineer Feedback (improves the model)")
    with st.form("feedback_form"):
        usefulness = st.slider("How useful was this output?", 1, 5, 4)
        was_edited = st.checkbox("I would edit/correct this before use")
        what_improve = st.text_area("What should be improved?", height=70)
        why_changes = st.text_area(
            "If you'd change the design/profile, what and why?", height=70)
        submitted = st.form_submit_button("💾 Submit feedback")
        if submitted:
            rec = save_feedback({
                "inputs": res["inputs"],
                "fixture_spec": res["spec"].to_dict(),
                "profile": res["profile_dict"],
                "usefulness": usefulness,
                "was_edited": was_edited,
                "what_improve": what_improve,
                "why_changes": why_changes,
            })
            if rec["ok"]:
                st.success(f"Feedback saved (id {rec['id'][:8]}). "
                           "This becomes a training example.")
            else:
                st.error(f"Save failed: {rec['error']}")

    stats = feedback_stats()
    if stats["count"]:
        st.caption(f"Feedback collected: {stats['count']} · "
                   f"avg usefulness {stats['avg_usefulness']} · "
                   f"edited fraction {stats['edited_fraction']}")
