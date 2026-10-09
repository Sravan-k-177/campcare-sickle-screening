"""Shared UI helpers: status badges and small cards used across camp pages."""

from __future__ import annotations

import streamlit as st

STATUS_COLORS = {
    "Registered": "blue",
    "In progress": "orange",
    "Screened": "violet",
    "Referred": "red",
    "Completed": "green",
}

TRIAGE_COLORS = {"Green": "green", "Yellow": "orange", "Red": "red"}


def status_badge(status: str) -> None:
    st.badge(status, color=STATUS_COLORS.get(status, "gray"))


def triage_badge(band: str) -> None:
    icon = ":material/check_circle:" if band == "Green" else ":material/warning:"
    st.badge(f"Triage: {band}", icon=icon, color=TRIAGE_COLORS.get(band, "gray"))


def result_badge(result: str) -> None:
    color = "red" if result == "Positive" else "green"
    icon = ":material/error:" if result == "Positive" else ":material/check_circle:"
    st.badge(result, icon=icon, color=color)


def token_card(token: str, name: str) -> None:
    with st.container(border=True):
        st.markdown(f"### {token}")
        st.markdown(f"**{name}** — please proceed to the vitals desk")
