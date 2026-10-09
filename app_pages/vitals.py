"""Vitals — triage station: capture vitals, auto-compute BMI and triage band."""

import streamlit as st

from camp.care import bmi, bp_class, triage_band
from camp.db import latest_vitals, list_patients, save_vitals, set_status
from camp.ui import triage_badge

patients = list_patients(limit=300)
if not patients:
    st.caption("No patients yet. Register someone first.")
    st.page_link("app_pages/register.py", label="Go to registration", icon=":material/person_add:")
    st.stop()

options = {p["id"]: f"{p['token']} — {p['name']}" for p in patients}
patient_id = st.selectbox("Patient", options=list(options), format_func=options.get, key="vitals_patient")
patient = next(p for p in patients if p["id"] == patient_id)

with st.container(border=True):
    st.markdown(f"**{patient['token']} — {patient['name']}**")
    st.caption(
        f"{patient.get('age') or '-'} yrs • {patient.get('sex') or '-'} • "
        f"{patient.get('village') or '-'} • Status: {patient['status']}"
    )

previous = latest_vitals(patient_id)
if previous:
    st.caption(
        f"Last vitals: BP {previous.get('bp_sys') or '-'}/{previous.get('bp_dia') or '-'} • "
        f"SpO2 {previous.get('spo2') or '-'}% • Hb {previous.get('hb') or '-'} • "
        f"{previous.get('created_at', '')}"
    )
    triage_badge(previous.get("triage", "Green"))

st.subheader("Capture vitals", icon=":material/monitor_heart:")
with st.form("vitals_form"):
    col_a, col_b = st.columns(2)
    with col_a:
        height = st.number_input("Height (cm)", min_value=30.0, max_value=230.0, value=None, placeholder="e.g. 162")
    with col_b:
        weight = st.number_input("Weight (kg)", min_value=2.0, max_value=250.0, value=None, placeholder="e.g. 58")
    col_c, col_d = st.columns(2)
    with col_c:
        bp_sys = st.number_input("BP systolic", min_value=50, max_value=280, value=None, placeholder="e.g. 120")
    with col_d:
        bp_dia = st.number_input("BP diastolic", min_value=30, max_value=180, value=None, placeholder="e.g. 80")
    col_e, col_f = st.columns(2)
    with col_e:
        spo2 = st.number_input("SpO2 (%)", min_value=50.0, max_value=100.0, value=None, placeholder="e.g. 98")
    with col_f:
        pulse = st.number_input("Pulse (/min)", min_value=25, max_value=220, value=None, placeholder="e.g. 78")
    col_g, col_h = st.columns(2)
    with col_g:
        temp = st.number_input("Temp (°F)", min_value=90.0, max_value=110.0, value=None, placeholder="e.g. 98.6")
    with col_h:
        hb = st.number_input("Hb (g/dL)", min_value=2.0, max_value=22.0, value=None, placeholder="Point-of-care Hb")
    col_i, col_j = st.columns(2)
    with col_i:
        pallor = st.checkbox("Pallor observed")
    with col_j:
        edema = st.checkbox("Edema observed")
    notes = st.text_area("Triage notes", placeholder="Anything the MO should know", height=70)
    saved = st.form_submit_button("Save vitals", type="primary")

if saved:
    record = {
        "height_cm": height,
        "weight_kg": weight,
        "bmi": bmi(height, weight),
        "bp_sys": bp_sys,
        "bp_dia": bp_dia,
        "spo2": spo2,
        "pulse": pulse,
        "temp_f": temp,
        "hb": hb,
        "pallor": pallor,
        "edema": edema,
        "notes": notes.strip(),
    }
    band, reasons = triage_band(record)
    record["triage"] = band
    save_vitals(patient_id, record)
    if patient["status"] == "Registered":
        set_status(patient_id, "In progress")
    st.toast(f"Vitals saved — triage {band}")

    with st.container(border=True):
        triage_badge(band)
        if record["bmi"]:
            st.markdown(f"**BMI:** {record['bmi']}  •  **BP:** {bp_class(bp_sys, bp_dia)}")
        else:
            st.markdown(f"**BP:** {bp_class(bp_sys, bp_dia)}")
        for reason in reasons:
            st.markdown(f"- {reason}")
        if not reasons:
            st.caption("All vitals within expected range.")
        if band == "Red":
            st.error("Red flag — stabilize, inform the medical officer, and consider urgent referral.", icon=":material/siren:")
        elif band == "Yellow":
            st.warning("Needs MO review before the person leaves the camp.", icon=":material/warning:")
    st.page_link("app_pages/screen.py", label="Continue to AI screening", icon=":material/biotech:")
