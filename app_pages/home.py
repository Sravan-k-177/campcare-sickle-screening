"""Home — today's camp dashboard: KPIs, live queue, throughput, quick actions."""

import streamlit as st

from camp.care import CAMP_CHECKLIST
from camp.db import camp_stats, queue_today

stats = camp_stats()

with st.container(horizontal=True):
    st.metric("Registered", stats["registered"], border=True)
    st.metric("In queue", stats["in_queue"], border=True)
with st.container(horizontal=True):
    st.metric("AI screened", stats["screened"], border=True)
    st.metric("Positives", stats["positives"], f"{stats['positivity']}% rate", border=True)
with st.container(horizontal=True):
    st.metric("Referred", stats["referred"], border=True)
    st.metric("Red triage", stats["red_flags"], border=True)

st.subheader("Now serving", icon=":material/campaign:")
queue = queue_today()
if queue:
    first = queue[0]
    with st.container(border=True):
        st.markdown(f"### {first['token']} — {first['name']}")
        st.caption(f"{len(queue)} waiting  •  {first.get('village') or 'village not recorded'}")
    st.page_link("app_pages/vitals.py", label="Send to vitals", icon=":material/monitor_heart:")
else:
    st.caption("Queue is clear. Register the next person to keep the camp moving.")

st.subheader("Live queue", icon=":material/groups:")
if queue:
    st.dataframe(
        [{"Token": p["token"], "Name": p["name"], "Status": p["status"]} for p in queue[:10]],
        hide_index=True,
        width="stretch",
    )
else:
    st.caption("No one waiting right now.")

st.subheader("Registrations by hour", icon=":material/bar_chart:")
if stats["hourly"]:
    st.bar_chart(stats["hourly"], x="hour", y="registrations", alt="Registrations per hour")
else:
    st.caption("Today's footfall chart will appear after the first registration.")

st.subheader("Jump to station", icon=":material/bolt:")
col_a, col_b = st.columns(2)
with col_a:
    st.page_link("app_pages/register.py", label="Register", icon=":material/person_add:")
    st.page_link("app_pages/vitals.py", label="Vitals", icon=":material/monitor_heart:")
with col_b:
    st.page_link("app_pages/screen.py", label="Screen", icon=":material/biotech:")
    st.page_link("app_pages/records.py", label="Records", icon=":material/folder:")

with st.expander("Camp readiness checklist", icon=":material/checklist:"):
    for i, item in enumerate(CAMP_CHECKLIST):
        st.checkbox(item, key=f"check_{i}")
