"""More — model card, counseling library, data management, about."""

import streamlit as st

from camp.ai import load_model
from camp.care import ABOUT_MODEL, COUNSEL_NEGATIVE, COUNSEL_POSITIVE, DISCLAIMER
from camp.db import camp_stats, cases_to_csv, counts, fetch_cases, list_patients, patients_to_csv
from camp.store import save_settings

st.subheader("AI model", icon=":material/biotech:")
calibrated = None
try:
    _, device, calibrated = load_model()
    with st.container(border=True):
        st.markdown("**CurveCircleNet — sickle cell screening**")
        st.caption(f"Status: ready on {device} • calibrated threshold {calibrated:.2f}")
        st.caption(ABOUT_MODEL)
except Exception as err:
    st.error(f"Model unavailable: {err}", icon=":material/error:")

if calibrated is not None:
    with st.container(border=True):
        st.markdown("**Operating threshold for this session**")
        use_custom = st.toggle("Override calibrated threshold", value=st.session_state.ai_threshold is not None)
        if use_custom:
            st.session_state.ai_threshold = st.slider(
                "Custom threshold",
                min_value=0.10,
                max_value=0.90,
                value=float(st.session_state.ai_threshold or calibrated),
                step=0.01,
            )
            save_settings({"ai_threshold": float(st.session_state.ai_threshold)})
        elif st.session_state.ai_threshold is not None:
            st.session_state.ai_threshold = None
            save_settings({"ai_threshold": None})
            st.rerun()

st.subheader("Counseling library", icon=":material/chat:")
with st.expander("How to read the AI explanation", icon=":material/psychology:"):
    st.markdown(
        "- **Overlay heatmap** — red areas pushed the decision most. Check that red falls on cells, not on glare, dust, or slide edges.\n"
        "- **Crescent-edge vs round-symmetry bars** — the model's two evidence streams. Edge dominance with a Positive call means sickle-like boundaries were found; symmetry dominance with Negative means healthy round cells.\n"
        "- **Borderline calls** (within 15 points of the threshold) deserve a retake and lab confirmation before any action."
    )
for counsel in (COUNSEL_POSITIVE, COUNSEL_NEGATIVE):
    with st.expander(counsel["title"]):
        for point in counsel["points"]:
            st.markdown(f"- {point}")
        st.caption(f"Hindi: {counsel['hindi']}")

st.subheader("Camp data", icon=":material/database:")
stats = camp_stats()
totals = counts()
with st.container(horizontal=True):
    st.metric("Patients (all time)", totals["patients"], border=True)
    st.metric("Vitals saved", totals["vitals"], border=True)
with st.container(horizontal=True):
    st.metric("AI cases (all time)", totals["screenings"], border=True)
    st.metric("Screened today", stats["screened"], border=True)
st.caption("Data is stored on this device (offline-first). Export before leaving the camp.")

col_a, col_b = st.columns(2)
with col_a:
    st.download_button(
        "Patients CSV",
        data=patients_to_csv(list_patients(limit=5000)),
        file_name="camp_patients_full.csv",
        mime="text/csv",
        icon=":material/download:",
    )
with col_b:
    st.download_button(
        "Screenings CSV",
        data=cases_to_csv(fetch_cases(limit=5000)),
        file_name="camp_screenings_full.csv",
        mime="text/csv",
        icon=":material/download:",
    )

st.subheader("About", icon=":material/info:")
st.caption(
    "CampCare stations: Home (dashboard) → Register (tokens + queue) → Vitals (triage) → "
    "Screen (AI microscopy) → Records (review + export). Built for low-connectivity field camps."
)
st.caption(DISCLAIMER)
