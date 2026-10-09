"""Records — search patients and AI screenings, review details, export for reports."""

import streamlit as st

from camp.db import (
    cases_to_csv,
    fetch_case_images,
    fetch_cases,
    latest_vitals,
    list_patients,
    patients_to_csv,
    screenings_for_token,
    set_status,
    STATUS_CHOICES,
)
from camp.ui import result_badge, status_badge, triage_badge

tab_patients, tab_ai = st.tabs(["Patients", "AI screenings"])

# ------------------------------------------------------------- patients ---
with tab_patients:
    query = st.text_input("Search", placeholder="Name, token, phone, village", key="rec_q")
    status_filter = st.segmented_control(
        "Status", ["All", *STATUS_CHOICES], default="All", key="rec_status"
    )
    patients = list_patients(status=status_filter, query=query)

    if not patients:
        st.caption("No patient records found.")
    else:
        st.dataframe(
            [
                {
                    "Token": p["token"],
                    "Name": p["name"],
                    "Age": p.get("age") or "-",
                    "Village": p.get("village") or "-",
                    "Status": p["status"],
                    "Triage": p.get("latest_triage") or "-",
                }
                for p in patients[:100]
            ],
            hide_index=True,
            width="stretch",
        )
        st.download_button(
            "Export patients (CSV)",
            data=patients_to_csv(patients),
            file_name="camp_patients.csv",
            mime="text/csv",
            icon=":material/download:",
        )
        options = {p["id"]: f"{p['token']} — {p['name']}" for p in patients[:100]}
        selected = st.selectbox("Open record", options=list(options), format_func=options.get)
        p = next(x for x in patients if x["id"] == selected)

        with st.container(border=True):
            st.markdown(f"### {p['token']} — {p['name']}")
            status_badge(p["status"])
            st.markdown(
                f"**Age/sex:** {p.get('age') or '-'} / {p.get('sex') or '-'}  \n"
                f"**Phone:** {p.get('phone') or '-'} • **Village:** {p.get('village') or '-'}  \n"
                f"**ABHA:** {p.get('abha_id') or '-'}  \n"
                f"**Family history:** {p.get('family_history') or 'None recorded'}  \n"
                f"**Symptoms:** {p.get('symptoms') or 'None recorded'}"
            )
            if p.get("referral_note"):
                st.caption(f"Referral: {p['referral_note']}")

        vitals = latest_vitals(selected)
        with st.container(border=True):
            st.markdown("**Latest vitals**")
            if vitals:
                triage_badge(vitals.get("triage", "Green"))
                st.markdown(
                    f"BP {vitals.get('bp_sys') or '-'}/{vitals.get('bp_dia') or '-'} • "
                    f"SpO2 {vitals.get('spo2') or '-'}% • Pulse {vitals.get('pulse') or '-'} • "
                    f"Temp {vitals.get('temp_f') or '-'}°F • Hb {vitals.get('hb') or '-'} • "
                    f"BMI {vitals.get('bmi') or '-'}"
                )
                if vitals.get("notes"):
                    st.caption(vitals["notes"])
            else:
                st.caption("No vitals captured yet.")

        history = screenings_for_token(p["token"])
        with st.container(border=True):
            st.markdown("**AI screenings**")
            if history:
                for case in history:
                    result_badge(case["case_result"])
                    st.caption(
                        f"{case['case_id']} • {case['timestamp']} • "
                        f"max {case['max_sickle_probability'] * 100:.1f}% • "
                        f"{case['images_processed']} field(s)"
                    )
            else:
                st.caption("Not screened yet.")

        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("Mark completed", icon=":material/check:"):
                set_status(selected, "Completed")
                st.toast("Marked completed")
                st.rerun()
        with col_b:
            if st.button("Mark referred", icon=":material/forward_to_inbox:"):
                set_status(selected, "Referred", referral_note="Marked from records")
                st.toast("Marked referred")
                st.rerun()

# ------------------------------------------------------------------ AI ---
with tab_ai:
    ai_query = st.text_input("Search screenings", placeholder="Name or token", key="ai_q")
    ai_filter = st.segmented_control("Result", ["All", "Positive", "Negative"], default="All", key="ai_f")
    cases = fetch_cases(person_query=ai_query, result_filter=ai_filter)

    if not cases:
        st.caption("No screening records found.")
    else:
        st.dataframe(
            [
                {
                    "Case": c["case_id"][-12:],
                    "When": c["timestamp"],
                    "Person": c["person_name"],
                    "Token": c["person_id"],
                    "Max %": round(c["max_sickle_probability"] * 100, 1),
                    "Result": c["case_result"],
                }
                for c in cases
            ],
            hide_index=True,
            width="stretch",
        )
        st.download_button(
            "Export screenings (CSV)",
            data=cases_to_csv(cases),
            file_name="camp_screenings.csv",
            mime="text/csv",
            icon=":material/download:",
        )
        case_options = {c["case_id"]: f"{c['case_id'][-12:]} • {c['person_name']}" for c in cases}
        case_id = st.selectbox("Case detail", options=list(case_options), format_func=case_options.get)
        images = fetch_case_images(case_id)
        if images:
            st.dataframe(
                [
                    {
                        "Field": r["image_index"],
                        "File": r["source_name"],
                        "Sickle %": round(r["sickle_probability"] * 100, 2),
                        "Result": r["result"],
                    }
                    for r in images
                ],
                hide_index=True,
                width="stretch",
            )
