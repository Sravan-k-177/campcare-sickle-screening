"""Screen — AI microscope screening with CurveCircleNet, QC, referral and slip."""

import json
import uuid
from datetime import datetime

import streamlit as st
from PIL import Image

from camp.ai import load_model, predict, qc_check, spectrum
from camp.care import COUNSEL_NEGATIVE, COUNSEL_POSITIVE, REFERRAL_OPTIONS
from camp.db import list_patients, set_status, store_case_record
from camp.ui import result_badge
from camp.xai import explain_field, overlay, rationale_text

# --- model ------------------------------------------------------------------
try:
    model, device, calibrated = load_model()
except Exception as err:
    st.error(f"AI model failed to load: {err}", icon=":material/error:")
    st.caption("Place curvecirclenet_sickle_best.pth next to app.py and reload.")
    st.stop()

threshold = st.session_state.ai_threshold or calibrated
st.caption(f"CurveCircleNet ready on {device} • operating threshold {threshold:.2f}")
with st.expander("AI settings", icon=":material/tune:"):
    threshold = st.slider(
        "Decision threshold",
        min_value=0.10,
        max_value=0.90,
        value=float(threshold),
        step=0.01,
        help="Default is the calibrated threshold from validation.",
    )

# --- patient -----------------------------------------------------------------
patients = list_patients(limit=300)
if not patients:
    st.caption("No patients yet. Register someone first.")
    st.page_link("app_pages/register.py", label="Go to registration", icon=":material/person_add:")
    st.stop()

options = {p["id"]: f"{p['token']} — {p['name']} ({p['status']})" for p in patients}
patient_id = st.selectbox("Patient", options=list(options), format_func=options.get, key="screen_patient")
patient = next(p for p in patients if p["id"] == patient_id)
with st.container(border=True):
    st.markdown(f"**{patient['token']} — {patient['name']}**")
    st.caption(f"Status: {patient['status']} • Triage: {patient.get('latest_triage') or 'not recorded'}")

# --- capture ------------------------------------------------------------------
st.subheader("Capture fields", icon=":material/photo_camera:")
uploads = st.file_uploader(
    "Upload smear photos",
    type=["jpg", "jpeg", "png", "bmp"],
    accept_multiple_files=True,
    label_visibility="collapsed",
)
camera = st.camera_input("Or capture with camera", label_visibility="collapsed")
run = st.button("Run AI screening", type="primary", icon=":material/biotech:")

if not run:
    st.stop()

sources = [(f.name, f) for f in uploads or []]
if camera is not None:
    sources.append((camera.name or "camera_capture.jpg", camera))
if not sources:
    st.warning("Add at least one photo — upload or camera.")
    st.stop()

# --- inference + explanation ----------------------------------------------------
results = []
for idx, (fname, fobj) in enumerate(sources, start=1):
    out = predict(Image.open(fobj), model, device)
    qc = qc_check(out["resized"])
    sickle_prob = out["sickle_prob"]
    is_sickle = sickle_prob >= threshold
    xp = explain_field(model, out["tensor"], target=1 if is_sickle else 0)
    margin = sickle_prob - threshold
    results.append(
        {
            "index": idx,
            "source_name": fname,
            "clear_prob": out["clear_prob"],
            "sickle_prob": sickle_prob,
            "is_sickle": is_sickle,
            "margin": margin,
            "raw": out["raw"],
            "spectrum": spectrum(out["resized"]),
            "overlay": overlay(out["resized"], xp["cam"]),
            "gate_curv": xp["gate_curv"],
            "gate_circ": xp["gate_circ"],
            "why": rationale_text(is_sickle, xp["gate_curv"], xp["gate_circ"], margin),
            "qc": qc,
        }
    )

max_prob = max(r["sickle_prob"] for r in results)
case_positive = any(r["is_sickle"] for r in results)

with st.container(border=True):
    if case_positive:
        st.markdown("### :red[Positive — sickle morphology detected]")
        st.caption("At least one field crossed the decision threshold. Confirm per guidelines.")
    else:
        st.markdown("### :green[Negative — no sickle morphology]")
        st.caption("All fields stayed below the decision threshold.")
    st.progress(float(max_prob))
    st.caption(f"Highest sickle probability: {max_prob * 100:.1f}% across {len(results)} field(s)")

st.subheader("Per-field results", icon=":material/grid_view:")
warned = False
for r in results:
    label = "Positive" if r["is_sickle"] else "Negative"
    with st.expander(f"Field {r['index']} • {label} • {r['sickle_prob'] * 100:.1f}%", expanded=len(results) == 1):
        if not r["qc"]["ok"]:
            warned = True
            for w in r["qc"]["warnings"]:
                st.warning(w, icon=":material/photo:")
        st.image(r["raw"], caption="Microscope field", width="stretch", alt="Microscope field of view")
        with st.container(horizontal=True):
            st.metric("Sickle", f"{r['sickle_prob'] * 100:.1f}%", border=True)
            st.metric("Clear", f"{r['clear_prob'] * 100:.1f}%", border=True)
        st.progress(float(r["sickle_prob"]))
        st.image(r["overlay"], caption="Explainability overlay — red drove the decision", width="stretch", alt="Grad-CAM explanation overlay")
        with st.expander("Why this decision?", icon=":material/psychology:"):
            st.caption("Crescent-edge evidence (sickle cues)")
            st.progress(float(r["gate_curv"]))
            st.caption("Round-symmetry evidence (healthy cues)")
            st.progress(float(r["gate_circ"]))
            for point in r["why"]:
                st.markdown(f"- {point}")
        st.image(r["spectrum"], caption="Frequency-domain (Fourier) view", width="stretch", alt="Fourier spectrum")
        st.caption(
            f"Focus score {r['qc']['blur']} • brightness {r['qc']['brightness']}"
            + (" — retake advised" if not r["qc"]["ok"] else " — quality OK")
        )
if warned:
    st.caption("Tip: blurry or badly lit fields lower trust — retake and re-run before deciding.")

# --- save + act ------------------------------------------------------------------
profile = st.session_state.camp_profile
case_record = {
    "case_id": f"CASE-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6].upper()}",
    "timestamp": datetime.now().isoformat(timespec="seconds"),
    "person_name": patient["name"],
    "person_id": patient["token"],
    "age": str(patient.get("age") or "Not provided"),
    "notes": "",
    "camp_location": f"{profile.get('camp', '')} {profile.get('site', '')}".strip(),
    "operator_name": profile.get("operator", ""),
    "images_processed": len(results),
    "threshold": round(float(threshold), 2),
    "max_sickle_probability": round(max_prob, 6),
    "case_result": "Positive" if case_positive else "Negative",
    "image_details": [
        {
            "image_index": r["index"],
            "source_type": "Camp capture",
            "source_name": r["source_name"],
            "sickle_probability": round(r["sickle_prob"], 6),
            "clear_probability": round(r["clear_prob"], 6),
            "result": "Positive" if r["is_sickle"] else "Negative",
            "explanation": (
                f"{'Positive' if r['is_sickle'] else 'Negative'}: "
                f"crescent-edge {r['gate_curv'] * 100:.0f}% vs "
                f"round-symmetry {r['gate_circ'] * 100:.0f}%; "
                f"margin {r['margin'] * 100:+.1f} pts vs threshold {threshold:.2f}"
            ),
        }
        for r in results
    ],
}
store_case_record(case_record)
if patient["status"] in ("Registered", "In progress"):
    set_status(patient_id, "Screened")
st.success(f"Saved {case_record['case_id']}")
result_badge(case_record["case_result"])

counsel = COUNSEL_POSITIVE if case_positive else COUNSEL_NEGATIVE
with st.expander("What to tell the person", icon=":material/chat:", expanded=True):
    st.markdown(f"**{counsel['title']}**")
    for point in counsel["points"]:
        st.markdown(f"- {point}")
    st.caption(f"Hindi: {counsel['hindi']}")

st.subheader("Referral", icon=":material/forward_to_inbox:")
referral = st.selectbox("Decision", REFERRAL_OPTIONS, label_visibility="collapsed")
if st.button("Save referral", icon=":material/save:"):
    case_record["notes"] = referral
    set_status(patient_id, "Referred", referral_note=f"{case_record['case_id']} • {referral}")
    st.toast("Referral recorded")
    st.rerun()

slip_text = (
    f"CAMP SCREENING SLIP — {case_record['case_id']}\n"
    f"Camp: {case_record['camp_location']} | Date: {case_record['timestamp']}\n"
    f"Token: {patient['token']} | Name: {patient['name']} | Age: {case_record['age']}\n"
    f"AI result: {case_record['case_result']} "
    f"(max sickle probability {max_prob * 100:.1f}%, threshold {threshold:.2f})\n"
    f"Decision: {referral}\n"
    f"Note: screening only — confirmatory test at referral centre required.\n"
)
col_a, col_b = st.columns(2)
with col_a:
    st.download_button(
        "Slip (text)",
        data=slip_text,
        file_name=f"slip_{patient['token']}.txt",
        mime="text/plain",
        icon=":material/print:",
    )
with col_b:
    st.download_button(
        "Report (JSON)",
        data=json.dumps(case_record, indent=2),
        file_name=f"screening_{patient['token']}.json",
        mime="application/json",
        icon=":material/download:",
    )
