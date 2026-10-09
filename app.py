import streamlit as st
from datetime import date

from camp.db import init_db
from camp.store import load_settings

st.set_page_config(
    page_title="CampCare — Sickle cell camp screening",
    page_icon=":material/local_hospital:",
    layout="centered",
)

# --- one-time setup -------------------------------------------------------
init_db()

saved = load_settings()
if "camp_profile" not in st.session_state:
    st.session_state.camp_profile = {
        "camp": saved.get("camp") or "Village Health Camp",
        "site": saved.get("site") or "",
        "operator": saved.get("operator") or "",
        "date": saved.get("date") or str(date.today()),
    }
if "ai_threshold" not in st.session_state:
    st.session_state.ai_threshold = saved.get("ai_threshold")

# --- light, mobile-first styling (compact column, big touch targets) ------
st.html(
    """
    <style>
      .block-container { max-width: 640px; padding-top: 1rem; }
      .stButton > button { min-height: 46px; border-radius: 14px; font-weight: 600; }
      [data-testid="stFormSubmitButton"] > button { min-height: 48px; border-radius: 14px; }
      input, select, textarea { border-radius: 12px !important; }
      [data-testid="stMetric"] { border-radius: 16px; }
    </style>
    """
)

# --- navigation -----------------------------------------------------------
page = st.navigation(
    [
        st.Page("app_pages/home.py", title="Home", icon=":material/home:"),
        st.Page("app_pages/register.py", title="Register", icon=":material/person_add:"),
        st.Page("app_pages/vitals.py", title="Vitals", icon=":material/monitor_heart:"),
        st.Page("app_pages/screen.py", title="Screen", icon=":material/biotech:"),
        st.Page("app_pages/records.py", title="Records", icon=":material/folder:"),
        st.Page("app_pages/more.py", title="More", icon=":material/menu:"),
    ],
    position="top",
)

st.title(page.title, icon=page.icon)
profile = st.session_state.camp_profile
camp_line = " • ".join(
    part for part in [profile.get("camp"), profile.get("operator"), profile.get("date")] if part
)
if camp_line:
    st.caption(f":material/location_on: {camp_line}  •  offline-ready")

page.run()
