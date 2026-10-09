"""Clinical helpers (BMI, triage bands) and camp content (counseling, checklists)."""

from __future__ import annotations

SYMPTOM_OPTIONS = [
    "Fatigue / weakness",
    "Joint or bone pain",
    "Pale skin / pallor",
    "Shortness of breath",
    "Frequent infections",
    "Delayed growth (child)",
    "Jaundice (yellow eyes)",
    "Swelling of hands/feet",
]

FAMILY_OPTIONS = [
    "Sickle cell in family",
    "Thalassemia in family",
    "Childhood anemia deaths",
    "Consanguineous parents",
]

REFERRAL_OPTIONS = [
    "Routine — recheck at PHC within 2 weeks",
    "Priority — PHC medical officer this week",
    "Urgent — refer to district hospital / sickle cell centre",
    "Emergency — stabilize and shift now",
]


def bmi(height_cm: float | None, weight_kg: float | None) -> float | None:
    if not height_cm or not weight_kg or height_cm <= 0:
        return None
    return round(weight_kg / ((height_cm / 100) ** 2), 1)


def bp_class(sys: int | None, dia: int | None) -> str:
    if sys is None or dia is None:
        return "Not recorded"
    if sys >= 180 or dia >= 110:
        return "Hypertensive crisis"
    if sys >= 140 or dia >= 90:
        return "High (Stage 2)"
    if sys >= 130 or dia >= 80:
        return "Elevated / Stage 1"
    if sys < 90 or dia < 60:
        return "Low"
    return "Normal"


def triage_band(v: dict) -> tuple[str, list[str]]:
    """Green / Yellow / Red band with reasons, from vitals dict."""
    reasons: list[str] = []
    band = "Green"
    spo2, sys, dia = v.get("spo2"), v.get("bp_sys"), v.get("bp_dia")
    temp, hb = v.get("temp_f"), v.get("hb")

    def escalate(level: str, reason: str):
        nonlocal band
        reasons.append(reason)
        order = {"Green": 0, "Yellow": 1, "Red": 2}
        if order[level] > order[band]:
            band = level

    if spo2 is not None:
        if spo2 < 94:
            escalate("Red", f"Low SpO2 ({spo2}%)")
        elif spo2 < 96:
            escalate("Yellow", f"Borderline SpO2 ({spo2}%)")
    if sys is not None and dia is not None:
        if sys >= 180 or dia >= 110:
            escalate("Red", f"Hypertensive crisis ({sys}/{dia})")
        elif sys >= 160 or dia >= 100:
            escalate("Yellow", f"High BP ({sys}/{dia})")
        elif sys < 90:
            escalate("Yellow", f"Low BP ({sys}/{dia})")
    if temp is not None:
        if temp >= 103:
            escalate("Red", f"High fever ({temp}°F)")
        elif temp >= 100.4:
            escalate("Yellow", f"Fever ({temp}°F)")
    if hb is not None:
        if hb < 7:
            escalate("Red", f"Severe anemia suspicion (Hb {hb} g/dL)")
        elif hb < 10:
            escalate("Yellow", f"Moderate anemia suspicion (Hb {hb} g/dL)")
    if v.get("pallor"):
        escalate("Yellow", "Pallor observed")
    return band, reasons


COUNSEL_POSITIVE = {
    "title": "Screening suggests sickle morphology — what to say",
    "points": [
        "This is a screening result, not a final diagnosis. A confirmatory test (HPLC / electrophoresis) at the PHC or district hospital is needed.",
        "Sickle cell is inherited and manageable — regular follow-up, hydration, folic acid as advised, and timely care during pain episodes.",
        "Avoid triggers: dehydration, extreme cold/heat, infections, exhaustion, smoking/alcohol.",
        "Seek urgent care for: severe pain not settling, breathing difficulty, fever above 101°F, pale/limp child, or sudden weakness.",
        "Carry this camp slip to the referral centre. Family screening (siblings, spouse) is recommended.",
    ],
    "hindi": "यह जाँच (स्क्रीनिंग) है, पक्का निदान नहीं। PHC/जिला अस्पताल में HPLC जाँच कराएँ। पर्याप्त पानी पिएँ, डॉक्टर की सलाह मानें, दर्द/बुखार/साँस फूलने पर तुरंत अस्पताल जाएँ। यह पर्ची साथ ले जाएँ।",
}

COUNSEL_NEGATIVE = {
    "title": "Screening looks clear — what to say",
    "points": [
        "Today's AI screening did not detect sickle morphology.",
        "If symptoms (fatigue, pain episodes, pallor) persist, visit the PHC — other causes of anemia are common and treatable.",
        "Eat iron-rich foods, deworm as per schedule, and repeat screening at the next camp if advised.",
    ],
    "hindi": "आज की जाँच में सिकल सेल के लक्षण नहीं दिखे। थकान/दर्द/पीलापन बना रहे तो PHC जाएँ। आयरन युक्त भोजन लें।",
}

CAMP_CHECKLIST = [
    "Camp desk set: tokens, consent forms, referral slips",
    "Microscope + phone adapter cleaned, light source checked",
    "Vitals kit: BP cuff, pulse oximeter, thermometer, Hb meter",
    "Operator roster and camp location set in the app",
    "Data backup: export yesterday's CSV before starting",
]

ABOUT_MODEL = (
    "CurveCircleNet is a dual-stream network: a directional curvelet bank picks up "
    "crescent-shaped sickle boundaries in Fourier space, while circular-harmonic ring "
    "shells capture healthy discocyte symmetry. A gated fusion layer blends both streams "
    "before classification (Clear vs Sickle morphology)."
)

DISCLAIMER = (
    "For screening support at health camps only — not a substitute for laboratory "
    "diagnosis or medical advice. Positive screens must be confirmed per program "
    "guidelines and reviewed by a medical officer."
)
