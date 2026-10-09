"""SQLite storage for the medical-camp app.

Keeps the original screening tables (screening_cases / case_images) so any
existing records stay visible, and adds camp-workflow tables:

  patients  - camp registration + queue status
  vitals    - triage vitals captured at the vitals station
"""

from __future__ import annotations

import csv
import io
import sqlite3
from datetime import datetime

from camp.store import DB_FILE

DB_PATH = DB_FILE

STATUS_CHOICES = ["Registered", "In progress", "Screened", "Referred", "Completed"]

_SCHEMA = """
CREATE TABLE IF NOT EXISTS screening_cases (
    case_id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    person_name TEXT NOT NULL,
    person_id TEXT,
    age TEXT,
    notes TEXT,
    camp_location TEXT,
    operator_name TEXT,
    threshold REAL NOT NULL,
    max_sickle_probability REAL NOT NULL,
    case_result TEXT NOT NULL,
    images_processed INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS case_images (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id TEXT NOT NULL,
    image_index INTEGER NOT NULL,
    source_type TEXT NOT NULL,
    source_name TEXT NOT NULL,
    sickle_probability REAL NOT NULL,
    clear_probability REAL NOT NULL,
    result TEXT NOT NULL,
    FOREIGN KEY(case_id) REFERENCES screening_cases(case_id)
);
CREATE TABLE IF NOT EXISTS patients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    token TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    age INTEGER,
    sex TEXT,
    phone TEXT,
    village TEXT,
    abha_id TEXT,
    consent INTEGER NOT NULL DEFAULT 0,
    family_history TEXT DEFAULT '',
    symptoms TEXT DEFAULT '',
    camp TEXT DEFAULT '',
    operator_name TEXT DEFAULT '',
    status TEXT NOT NULL DEFAULT 'Registered',
    referral_note TEXT DEFAULT '',
    referred_at TEXT DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS vitals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER NOT NULL,
    height_cm REAL,
    weight_kg REAL,
    bmi REAL,
    bp_sys INTEGER,
    bp_dia INTEGER,
    spo2 REAL,
    pulse INTEGER,
    temp_f REAL,
    hb REAL,
    pallor INTEGER NOT NULL DEFAULT 0,
    edema INTEGER NOT NULL DEFAULT 0,
    triage TEXT DEFAULT 'Green',
    notes TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    FOREIGN KEY(patient_id) REFERENCES patients(id)
);
"""

_READY: set[str] = set()


def _connect(db_path: str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    if db_path not in _READY:
        conn.executescript(_SCHEMA)  # self-healing: every page works standalone
        conn.commit()
        _READY.add(db_path)
    return conn


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def today_prefix() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def init_db(db_path: str = DB_PATH) -> None:
    """Explicit schema init (also happens automatically on first use)."""
    with _connect(db_path):
        pass


# ---------------------------------------------------------------- patients
def next_token(db_path: str = DB_PATH) -> str:
    """Next queue token for today, e.g. T-001, T-002."""
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM patients WHERE substr(created_at, 1, 10) = ?",
            (today_prefix(),),
        ).fetchone()
    return f"T-{(row['n'] + 1):03d}"


def create_patient(record: dict, db_path: str = DB_PATH) -> str:
    token = next_token(db_path)
    with _connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO patients (token, name, age, sex, phone, village, abha_id,
                                  consent, family_history, symptoms, camp,
                                  operator_name, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Registered', ?)
            """,
            (
                token,
                record["name"],
                record.get("age"),
                record.get("sex", ""),
                record.get("phone", ""),
                record.get("village", ""),
                record.get("abha_id", ""),
                1 if record.get("consent") else 0,
                record.get("family_history", ""),
                record.get("symptoms", ""),
                record.get("camp", ""),
                record.get("operator_name", ""),
                now_iso(),
            ),
        )
    return token


def list_patients(
    status: str = "All",
    query: str = "",
    limit: int = 300,
    db_path: str = DB_PATH,
) -> list[dict]:
    conditions, params = [], []
    if status != "All":
        conditions.append("p.status = ?")
        params.append(status)
    if query.strip():
        conditions.append("(p.name LIKE ? OR p.token LIKE ? OR p.phone LIKE ? OR p.village LIKE ?)")
        pattern = f"%{query.strip()}%"
        params.extend([pattern] * 4)
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    with _connect(db_path) as conn:
        rows = conn.execute(
            f"""
            SELECT p.*, v.triage AS latest_triage
            FROM patients p
            LEFT JOIN vitals v ON v.id = (
                SELECT id FROM vitals WHERE patient_id = p.id ORDER BY id DESC LIMIT 1
            )
            {where}
            ORDER BY p.id DESC LIMIT ?
            """,
            (*params, limit),
        ).fetchall()
    return [dict(r) for r in rows]


def queue_today(db_path: str = DB_PATH) -> list[dict]:
    """Patients still in the camp queue (registered / in progress), oldest first."""
    with _connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT * FROM patients
            WHERE status IN ('Registered', 'In progress')
              AND substr(created_at, 1, 10) = ?
            ORDER BY id ASC
            """,
            (today_prefix(),),
        ).fetchall()
    return [dict(r) for r in rows]


def get_patient(patient_id: int, db_path: str = DB_PATH) -> dict | None:
    with _connect(db_path) as conn:
        row = conn.execute("SELECT * FROM patients WHERE id = ?", (patient_id,)).fetchone()
    return dict(row) if row else None


def set_status(patient_id: int, status: str, referral_note: str = "", db_path: str = DB_PATH) -> None:
    with _connect(db_path) as conn:
        if status == "Referred":
            conn.execute(
                "UPDATE patients SET status = ?, referral_note = ?, referred_at = ? WHERE id = ?",
                (status, referral_note, now_iso(), patient_id),
            )
        else:
            conn.execute("UPDATE patients SET status = ? WHERE id = ?", (status, patient_id))


# ---------------------------------------------------------------- vitals
def save_vitals(patient_id: int, record: dict, db_path: str = DB_PATH) -> None:
    with _connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO vitals (patient_id, height_cm, weight_kg, bmi, bp_sys, bp_dia,
                                spo2, pulse, temp_f, hb, pallor, edema, triage, notes, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                patient_id,
                record.get("height_cm"),
                record.get("weight_kg"),
                record.get("bmi"),
                record.get("bp_sys"),
                record.get("bp_dia"),
                record.get("spo2"),
                record.get("pulse"),
                record.get("temp_f"),
                record.get("hb"),
                1 if record.get("pallor") else 0,
                1 if record.get("edema") else 0,
                record.get("triage", "Green"),
                record.get("notes", ""),
                now_iso(),
            ),
        )


def latest_vitals(patient_id: int, db_path: str = DB_PATH) -> dict | None:
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM vitals WHERE patient_id = ? ORDER BY id DESC LIMIT 1",
            (patient_id,),
        ).fetchone()
    return dict(row) if row else None


# ------------------------------------------------------- screening (legacy)
def store_case_record(case_record: dict, db_path: str = DB_PATH) -> None:
    with _connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO screening_cases (
                case_id, timestamp, person_name, person_id, age, notes,
                camp_location, operator_name, threshold, max_sickle_probability,
                case_result, images_processed
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                case_record["case_id"],
                case_record["timestamp"],
                case_record["person_name"],
                case_record["person_id"],
                case_record["age"],
                case_record["notes"],
                case_record["camp_location"],
                case_record["operator_name"],
                case_record["threshold"],
                case_record["max_sickle_probability"],
                case_record["case_result"],
                case_record["images_processed"],
            ),
        )
        for image in case_record["image_details"]:
            conn.execute(
                """
                INSERT INTO case_images (
                    case_id, image_index, source_type, source_name,
                    sickle_probability, clear_probability, result
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    case_record["case_id"],
                    image["image_index"],
                    image["source_type"],
                    image["source_name"],
                    image["sickle_probability"],
                    image["clear_probability"],
                    image["result"],
                ),
            )


def fetch_cases(
    person_query: str = "",
    result_filter: str = "All",
    limit: int = 250,
    db_path: str = DB_PATH,
) -> list[dict]:
    conditions, params = [], []
    if person_query.strip():
        conditions.append("(person_name LIKE ? OR person_id LIKE ?)")
        pattern = f"%{person_query.strip()}%"
        params.extend([pattern, pattern])
    if result_filter in {"Positive", "Negative"}:
        conditions.append("case_result = ?")
        params.append(result_filter)
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    with _connect(db_path) as conn:
        rows = conn.execute(
            f"SELECT * FROM screening_cases {where} ORDER BY timestamp DESC LIMIT ?",
            (*params, limit),
        ).fetchall()
    return [dict(r) for r in rows]


def fetch_case_images(case_id: str, db_path: str = DB_PATH) -> list[dict]:
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM case_images WHERE case_id = ? ORDER BY image_index ASC",
            (case_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def screenings_for_token(token: str, db_path: str = DB_PATH) -> list[dict]:
    return fetch_cases(person_query=token, db_path=db_path)


# ------------------------------------------------------------------ stats
def camp_stats(db_path: str = DB_PATH) -> dict:
    day = today_prefix()
    with _connect(db_path) as conn:
        reg = conn.execute(
            "SELECT COUNT(*) n FROM patients WHERE substr(created_at,1,10)=?", (day,)
        ).fetchone()["n"]
        in_queue = conn.execute(
            "SELECT COUNT(*) n FROM patients WHERE status IN ('Registered','In progress')"
            " AND substr(created_at,1,10)=?",
            (day,),
        ).fetchone()["n"]
        referred = conn.execute(
            "SELECT COUNT(*) n FROM patients WHERE status='Referred' AND substr(created_at,1,10)=?",
            (day,),
        ).fetchone()["n"]
        screened = conn.execute(
            "SELECT COUNT(*) n FROM screening_cases WHERE substr(timestamp,1,10)=?", (day,)
        ).fetchone()["n"]
        positives = conn.execute(
            "SELECT COUNT(*) n FROM screening_cases WHERE case_result='Positive'"
            " AND substr(timestamp,1,10)=?",
            (day,),
        ).fetchone()["n"]
        red = conn.execute(
            "SELECT COUNT(*) n FROM vitals WHERE triage='Red' AND substr(created_at,1,10)=?",
            (day,),
        ).fetchone()["n"]
        hourly = conn.execute(
            """
            SELECT substr(created_at, 12, 2) AS hr, COUNT(*) AS n
            FROM patients WHERE substr(created_at,1,10)=?
            GROUP BY hr ORDER BY hr
            """,
            (day,),
        ).fetchall()
    positivity = round(100 * positives / screened, 1) if screened else 0.0
    return {
        "registered": reg,
        "in_queue": in_queue,
        "screened": screened,
        "positives": positives,
        "positivity": positivity,
        "referred": referred,
        "red_flags": red,
        "hourly": [{"hour": r["hr"], "registrations": r["n"]} for r in hourly],
    }


def counts(db_path: str = DB_PATH) -> dict:
    with _connect(db_path) as conn:
        p = conn.execute("SELECT COUNT(*) n FROM patients").fetchone()["n"]
        v = conn.execute("SELECT COUNT(*) n FROM vitals").fetchone()["n"]
        s = conn.execute("SELECT COUNT(*) n FROM screening_cases").fetchone()["n"]
    return {"patients": p, "vitals": v, "screenings": s}


# ----------------------------------------------------------------- export
def patients_to_csv(patients: list[dict]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        ["token", "name", "age", "sex", "phone", "village", "abha_id",
         "family_history", "symptoms", "camp", "operator_name", "status",
         "referral_note", "created_at"]
    )
    for p in patients:
        writer.writerow([p.get(k, "") for k in
                         ["token", "name", "age", "sex", "phone", "village", "abha_id",
                          "family_history", "symptoms", "camp", "operator_name", "status",
                          "referral_note", "created_at"]])
    return buffer.getvalue()


def cases_to_csv(cases: list[dict]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        ["case_id", "timestamp", "person_name", "person_id", "age", "camp_location",
         "operator_name", "threshold", "max_sickle_probability", "case_result",
         "images_processed", "notes"]
    )
    for row in cases:
        writer.writerow([row.get(k, "") for k in
                         ["case_id", "timestamp", "person_name", "person_id", "age",
                          "camp_location", "operator_name", "threshold",
                          "max_sickle_probability", "case_result", "images_processed", "notes"]])
    return buffer.getvalue()
