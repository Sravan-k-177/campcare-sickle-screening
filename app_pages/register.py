"""Register — camp session setup, patient registration, and queue control."""

import streamlit as st

from camp.care import FAMILY_OPTIONS, SYMPTOM_OPTIONS
from camp.db import STATUS_CHOICES, create_patient, list_patients, next_token, set_status
from camp.store import save_settings
from camp.ui import status_badge, token_card

# --- camp session ----------------------------------------------------------
with st.expander("Camp session", icon=":material/location_on:", expanded=False):
    profile = st.session_state.camp_profile
    with st.form("camp_form"):
        camp = st.text_input("Camp name", value=profile.get("camp", ""))
        site = st.text_input("Site / village", value=profile.get("site", ""))
        operator = st.text_input("Operator / MO name", value=profile.get("operator", ""))
        if st.form_submit_button("Save session"):
            st.session_state.camp_profile = {
                "camp": camp.strip() or "Village Health Camp",
                "site": site.strip(),
                "operator": operator.strip(),
                "date": profile.get("date"),
            }
            save_settings(
                {
                    "camp": st.session_state.camp_profile["camp"],
                    "site": st.session_state.camp_profile["site"],
                    "operator": st.session_state.camp_profile["operator"],
                    "date": st.session_state.camp_profile["date"],
                }
            )
            st.toast("Camp session saved — remembered after restart")

# --- new registration ------------------------------------------------------
st.subheader("New registration", icon=":material/person_add:")
st.caption(f"Next token: **{next_token()}**")

with st.form("patient_form"):
    name = st.text_input("Full name *", placeholder="e.g. Riya Sharma")
    col_a, col_b = st.columns(2)
    with col_a:
        age = st.number_input("Age", min_value=0, max_value=120, value=None, placeholder="Years")
    with col_b:
        sex = st.segmented_control("Sex", ["Female", "Male", "Other"], default="Female")
    col_c, col_d = st.columns(2)
    with col_c:
        phone = st.text_input("Phone", placeholder="10-digit mobile")
    with col_d:
        village = st.text_input("Village / ward", placeholder="e.g. Kothur")
    abha = st.text_input("ABHA / health ID (optional)", placeholder="e.g. 91-1234-5678-9012")
    family = st.multiselect("Family / risk history", FAMILY_OPTIONS)
    symptoms = st.multiselect("Current symptoms", SYMPTOM_OPTIONS)
    consent = st.checkbox("Consent taken for screening and data recording *")
    submitted = st.form_submit_button("Register and issue token", type="primary")

if submitted:
    if not name.strip():
        st.warning("Please enter the person's name.")
    elif not consent:
        st.warning("Consent is required before registration.")
    else:
        profile = st.session_state.camp_profile
        token = create_patient(
            {
                "name": name.strip(),
                "age": int(age) if age is not None else None,
                "sex": sex or "",
                "phone": phone.strip(),
                "village": village.strip(),
                "abha_id": abha.strip(),
                "consent": True,
                "family_history": ", ".join(family),
                "symptoms": ", ".join(symptoms),
                "camp": f"{profile.get('camp', '')} {profile.get('site', '')}".strip(),
                "operator_name": profile.get("operator", ""),
            }
        )
        st.toast(f"{token} registered")
        token_card(token, name.strip())

# --- queue control ----------------------------------------------------------
st.subheader("Queue", icon=":material/groups:")
query = st.text_input("Search queue", placeholder="Name, token, phone, village")
status_filter = st.segmented_control(
    "Status", ["All", "Registered", "In progress", "Screened"], default="All"
)
patients = list_patients(status=status_filter, query=query)

if not patients:
    st.caption("No patients match this filter.")
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
            for p in patients[:60]
        ],
        hide_index=True,
        width="stretch",
    )
    options = {p["id"]: f"{p['token']} — {p['name']} ({p['status']})" for p in patients[:60]}
    selected = st.selectbox(
        "Update patient",
        options=list(options),
        format_func=options.get,
        label_visibility="collapsed",
    )
    col_e, col_f = st.columns(2)
    with col_e:
        current = next(p["status"] for p in patients if p["id"] == selected)
        new_status = st.selectbox("Move to", STATUS_CHOICES, index=STATUS_CHOICES.index(current))
    with col_f:
        st.write("")
        if st.button("Update status", key="queue_update"):
            set_status(selected, new_status)
            st.toast(f"Moved to {new_status}")
            st.rerun()

    current_patient = next(p for p in patients if p["id"] == selected)
    status_badge(current_patient["status"])
