"""
SQLite persistence layer (single file, zero external services).

Family profiles: a family member is a row in `users` with owner_id pointing at
the account that manages it (no password: cannot log in). Every data table is
keyed by user_id, so "switching profile" simply changes which user_id the app
reads and writes: no module needs to know about families.

Swap get_conn() for a hosted Postgres connection for persistent deployment;
every function here is the only place that would change.
"""
import json
import os
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, date, timedelta, timezone

DB_PATH = os.path.join(os.path.dirname(__file__), "echocare.db")

DATA_TABLES = [
    "evidence_chunks", "story_entries", "survey_responses", "tracker_entries", "reports",
    "insights", "chat_messages", "specialist_opinions", "feedback", "vitals",
    "medicines", "medicine_logs", "appointments", "emergency_cards",
]


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _ensure_column(conn, table: str, column: str, decl: str):
    cols = [r["name"] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
    if column not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")


def init_db():
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL, created_at TEXT NOT NULL)""")
        c.execute("""CREATE TABLE IF NOT EXISTS evidence_chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, source_type TEXT NOT NULL,
            text TEXT NOT NULL, theme_tags TEXT NOT NULL, timestamp TEXT NOT NULL, metadata TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS story_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, text TEXT NOT NULL,
            extracted_symptoms TEXT NOT NULL, timeline TEXT, created_at TEXT NOT NULL)""")
        c.execute("""CREATE TABLE IF NOT EXISTS survey_responses (
            user_id INTEGER PRIMARY KEY, about_you TEXT, main_concern TEXT, care_context TEXT,
            step_complete INTEGER DEFAULT 0, updated_at TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS tracker_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, entry_date TEXT NOT NULL,
            sleep_hours REAL, water_glasses INTEGER, stress_level INTEGER, energy_level INTEGER,
            pain_level INTEGER, notes TEXT, updated_at TEXT, UNIQUE(user_id, entry_date))""")
        c.execute("""CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, filename TEXT,
            extraction_method TEXT, raw_text_excerpt TEXT, fields TEXT, created_at TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS insights (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, theme TEXT, text TEXT,
            confidence REAL, confidence_label TEXT, evidence_summary TEXT, evidence_chunk_ids TEXT,
            generated_by TEXT, created_at TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, role TEXT NOT NULL,
            content TEXT NOT NULL, is_emergency INTEGER DEFAULT 0, created_at TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS specialist_opinions (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, specialist_name TEXT,
            department TEXT, opinion_text TEXT, created_at TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, context TEXT,
            outcome TEXT, rating INTEGER, created_at TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS vitals (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, entry_date TEXT NOT NULL,
            weight_kg REAL, height_cm REAL, systolic INTEGER, diastolic INTEGER,
            fasting_sugar REAL, postmeal_sugar REAL, updated_at TEXT, UNIQUE(user_id, entry_date))""")
        c.execute("""CREATE TABLE IF NOT EXISTS medicines (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, name TEXT NOT NULL,
            dose TEXT, frequency TEXT, slots TEXT, start_date TEXT, end_date TEXT, notes TEXT,
            active INTEGER DEFAULT 1, created_at TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS medicine_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, medicine_id INTEGER NOT NULL,
            log_date TEXT NOT NULL, slot TEXT NOT NULL, taken INTEGER DEFAULT 1,
            UNIQUE(medicine_id, log_date, slot))""")
        c.execute("""CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, doctor_name TEXT,
            specialty TEXT, hospital TEXT, appt_date TEXT NOT NULL, appt_time TEXT, reason TEXT,
            notes TEXT, status TEXT DEFAULT 'scheduled', created_at TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS emergency_cards (
            user_id INTEGER PRIMARY KEY, data TEXT, token TEXT, public_enabled INTEGER DEFAULT 0,
            updated_at TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS doctors_imported (
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, specialty TEXT, district TEXT,
            hospital TEXT, lat REAL, lon REAL, rating REAL, years_experience INTEGER,
            consultation_fee_inr INTEGER, phone TEXT, imported_at TEXT)""")

        # additive migrations (safe on databases created by earlier versions)
        _ensure_column(conn, "users", "owner_id", "INTEGER")
        _ensure_column(conn, "users", "relation", "TEXT")
        _ensure_column(conn, "users", "dob", "TEXT")
        _ensure_column(conn, "evidence_chunks", "embedding", "TEXT")
        _ensure_column(conn, "reports", "report_date", "TEXT")
        _ensure_column(conn, "insights", "confidence_breakdown", "TEXT")
        _ensure_column(conn, "chat_messages", "kind", "TEXT")


def _now() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat()


# ======================= Users & family =======================
def create_user(name: str, email: str, password_hash: str, owner_id: int | None = None,
                relation: str | None = None, dob: str | None = None) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO users (name, email, password_hash, created_at, owner_id, relation, dob) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)", (name, email, password_hash, _now(), owner_id, relation, dob))
        return cur.lastrowid


def get_user_by_email(email: str):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        return dict(row) if row else None


def get_user_by_id(user_id: int):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None


def create_member(owner_id: int, name: str, relation: str, dob: str | None = None) -> int:
    email = f"member-{owner_id}-{secrets.token_hex(4)}@family.local"
    return create_user(name, email, "!", owner_id=owner_id, relation=relation, dob=dob)


def get_members(owner_id: int) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM users WHERE owner_id = ? ORDER BY id", (owner_id,)).fetchall()
        return [dict(r) for r in rows]


def delete_member(owner_id: int, member_id: int) -> bool:
    member = get_user_by_id(member_id)
    if not member or member.get("owner_id") != owner_id:
        return False
    delete_all_user_data(member_id)
    return True


# ======================= Evidence (LE-RAG) =======================
def insert_evidence_chunk(user_id: int, source_type: str, text: str, theme_tags: list,
                          metadata: dict | None = None, embedding: list | None = None) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO evidence_chunks (user_id, source_type, text, theme_tags, timestamp, metadata, embedding) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user_id, source_type, text, json.dumps(theme_tags), _now(), json.dumps(metadata or {}),
             json.dumps(embedding) if embedding else None))
        return cur.lastrowid


def _parse_chunk(row) -> dict:
    d = dict(row)
    d["theme_tags"] = json.loads(d["theme_tags"])
    d["metadata"] = json.loads(d["metadata"] or "{}")
    d["embedding"] = json.loads(d["embedding"]) if d.get("embedding") else None
    return d


def get_evidence_chunks(user_id: int) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM evidence_chunks WHERE user_id = ? ORDER BY id", (user_id,)).fetchall()
        return [_parse_chunk(r) for r in rows]


def get_evidence_chunks_by_ids(user_id: int, ids: list) -> list[dict]:
    ids = [int(i) for i in ids if str(i).isdigit()]
    if not ids:
        return []
    marks = ",".join("?" * len(ids))
    with get_conn() as conn:
        rows = conn.execute(
            f"SELECT * FROM evidence_chunks WHERE user_id = ? AND id IN ({marks}) ORDER BY timestamp",
            (user_id, *ids)).fetchall()
        return [_parse_chunk(r) for r in rows]


def update_chunk_embedding(chunk_id: int, embedding: list):
    with get_conn() as conn:
        conn.execute("UPDATE evidence_chunks SET embedding = ? WHERE id = ?", (json.dumps(embedding), chunk_id))


# ======================= Story =======================
def insert_story_entry(user_id: int, text: str, symptoms: list, timeline: str | None):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO story_entries (user_id, text, extracted_symptoms, timeline, created_at) VALUES (?,?,?,?,?)",
            (user_id, text, json.dumps(symptoms), timeline, _now()))


def get_story_entries(user_id: int) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM story_entries WHERE user_id = ? ORDER BY created_at DESC",
                            (user_id,)).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["extracted_symptoms"] = json.loads(d["extracted_symptoms"])
            out.append(d)
        return out


# ======================= Survey =======================
def upsert_survey(user_id: int, about_you: dict, main_concern: dict, care_context: dict, step_complete: int):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO survey_responses (user_id, about_you, main_concern, care_context, step_complete, updated_at) "
            "VALUES (?,?,?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET about_you=excluded.about_you, "
            "main_concern=excluded.main_concern, care_context=excluded.care_context, "
            "step_complete=excluded.step_complete, updated_at=excluded.updated_at",
            (user_id, json.dumps(about_you), json.dumps(main_concern), json.dumps(care_context),
             step_complete, _now()))


def get_survey(user_id: int):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM survey_responses WHERE user_id = ?", (user_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        for k in ("about_you", "main_concern", "care_context"):
            d[k] = json.loads(d[k] or "{}")
        return d


# ======================= Tracker =======================
def upsert_tracker_entry(user_id: int, entry_date: str, **fields):
    cols = ["sleep_hours", "water_glasses", "stress_level", "energy_level", "pain_level", "notes"]
    values = [fields.get(c) for c in cols]
    with get_conn() as conn:
        conn.execute(
            f"INSERT INTO tracker_entries (user_id, entry_date, {', '.join(cols)}, updated_at) "
            f"VALUES (?, ?, {', '.join(['?'] * len(cols))}, ?) ON CONFLICT(user_id, entry_date) DO UPDATE SET "
            + ", ".join(f"{c}=excluded.{c}" for c in cols) + ", updated_at=excluded.updated_at",
            (user_id, entry_date, *values, _now()))


def get_tracker_entry(user_id: int, entry_date: str):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM tracker_entries WHERE user_id = ? AND entry_date = ?",
                           (user_id, entry_date)).fetchone()
        return dict(row) if row else None


def get_tracker_range(user_id: int, start_date: str) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM tracker_entries WHERE user_id = ? AND entry_date >= ? "
                            "ORDER BY entry_date ASC", (user_id, start_date)).fetchall()
        return [dict(r) for r in rows]


def get_tracker_streak(user_id: int) -> int:
    with get_conn() as conn:
        rows = conn.execute("SELECT entry_date FROM tracker_entries WHERE user_id = ?", (user_id,)).fetchall()
    dates = {r["entry_date"] for r in rows}
    streak, cursor = 0, date.today()
    while cursor.isoformat() in dates:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


# ======================= Vitals =======================
VITAL_COLS = ["weight_kg", "height_cm", "systolic", "diastolic", "fasting_sugar", "postmeal_sugar"]


def upsert_vitals(user_id: int, entry_date: str, **fields):
    values = [fields.get(c) for c in VITAL_COLS]
    with get_conn() as conn:
        conn.execute(
            f"INSERT INTO vitals (user_id, entry_date, {', '.join(VITAL_COLS)}, updated_at) "
            f"VALUES (?, ?, {', '.join(['?'] * len(VITAL_COLS))}, ?) ON CONFLICT(user_id, entry_date) DO UPDATE SET "
            + ", ".join(f"{c}=excluded.{c}" for c in VITAL_COLS) + ", updated_at=excluded.updated_at",
            (user_id, entry_date, *values, _now()))


def get_vitals(user_id: int) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM vitals WHERE user_id = ? ORDER BY entry_date ASC", (user_id,)).fetchall()
        return [dict(r) for r in rows]


# ======================= Reports & labs =======================
def insert_report(user_id: int, filename: str, extraction_method: str, raw_text_excerpt: str,
                  fields: list, report_date: str | None = None):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO reports (user_id, filename, extraction_method, raw_text_excerpt, fields, created_at, report_date) "
            "VALUES (?,?,?,?,?,?,?)",
            (user_id, filename, extraction_method, raw_text_excerpt, json.dumps(fields), _now(),
             report_date or date.today().isoformat()))


def get_reports(user_id: int) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM reports WHERE user_id = ? ORDER BY report_date DESC, created_at DESC",
                            (user_id,)).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["fields"] = json.loads(d["fields"])
            d["report_date"] = d.get("report_date") or (d.get("created_at") or "")[:10]
            out.append(d)
        return out


# ======================= Insights =======================
def insert_insight(user_id: int, insight: dict):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO insights (user_id, theme, text, confidence, confidence_label, evidence_summary, "
            "evidence_chunk_ids, generated_by, created_at, confidence_breakdown) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (user_id, insight["theme"], insight["text"], insight["confidence"], insight["confidence_label"],
             insight["evidence_summary"], json.dumps(insight["evidence_chunk_ids"]), insight["generated_by"],
             _now(), json.dumps(insight.get("confidence_breakdown", {}))))


def get_insights(user_id: int) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM insights WHERE user_id = ? ORDER BY created_at DESC, id DESC",
                            (user_id,)).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["evidence_chunk_ids"] = json.loads(d["evidence_chunk_ids"] or "[]")
            d["confidence_breakdown"] = json.loads(d.get("confidence_breakdown") or "{}")
            out.append(d)
        return out


# ======================= Chat =======================
def insert_chat_message(user_id: int, role: str, content: str, is_emergency: bool = False, kind: str | None = None):
    with get_conn() as conn:
        conn.execute("INSERT INTO chat_messages (user_id, role, content, is_emergency, created_at, kind) "
                     "VALUES (?,?,?,?,?,?)", (user_id, role, content, int(is_emergency), _now(), kind))


def get_chat_history(user_id: int) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM chat_messages WHERE user_id = ? ORDER BY id ASC", (user_id,)).fetchall()
        return [dict(r) for r in rows]


# ======================= Diagnostic Guard =======================
def insert_specialist_opinion(user_id: int, specialist_name: str, department: str, opinion_text: str):
    with get_conn() as conn:
        conn.execute("INSERT INTO specialist_opinions (user_id, specialist_name, department, opinion_text, created_at) "
                     "VALUES (?,?,?,?,?)", (user_id, specialist_name, department, opinion_text, _now()))


def get_specialist_opinions(user_id: int) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM specialist_opinions WHERE user_id = ? ORDER BY id", (user_id,)).fetchall()
        return [dict(r) for r in rows]


# ======================= Feedback =======================
def insert_feedback(user_id: int, context: str, outcome: str, rating: int | None):
    with get_conn() as conn:
        conn.execute("INSERT INTO feedback (user_id, context, outcome, rating, created_at) VALUES (?,?,?,?,?)",
                     (user_id, context, outcome, rating, _now()))


def list_feedback(limit: int = 200) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT f.*, u.name AS user_name FROM feedback f LEFT JOIN users u ON u.id = f.user_id "
            "WHERE f.rating IS NOT NULL ORDER BY f.id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]


# ======================= Medicines =======================
def add_medicine(user_id: int, name: str, dose: str, frequency: str, slots: list, start_date: str,
                 end_date: str | None, notes: str = "") -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO medicines (user_id, name, dose, frequency, slots, start_date, end_date, notes, active, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,1,?)",
            (user_id, name, dose, frequency, json.dumps(slots), start_date, end_date, notes, _now()))
        return cur.lastrowid


def get_medicines(user_id: int, active_only: bool = True) -> list[dict]:
    q = "SELECT * FROM medicines WHERE user_id = ?" + (" AND active = 1" if active_only else "") + " ORDER BY id"
    with get_conn() as conn:
        rows = conn.execute(q, (user_id,)).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["slots"] = json.loads(d["slots"] or "[]")
            out.append(d)
        return out


def set_medicine_active(user_id: int, medicine_id: int, active: bool):
    with get_conn() as conn:
        conn.execute("UPDATE medicines SET active = ? WHERE id = ? AND user_id = ?",
                     (int(active), medicine_id, user_id))


def log_dose(user_id: int, medicine_id: int, log_date: str, slot: str, taken: bool):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO medicine_logs (user_id, medicine_id, log_date, slot, taken) VALUES (?,?,?,?,?) "
            "ON CONFLICT(medicine_id, log_date, slot) DO UPDATE SET taken = excluded.taken",
            (user_id, medicine_id, log_date, slot, int(taken)))


def get_dose_logs(user_id: int, start_date: str) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM medicine_logs WHERE user_id = ? AND log_date >= ?",
                            (user_id, start_date)).fetchall()
        return [dict(r) for r in rows]


# ======================= Appointments =======================
def add_appointment(user_id: int, doctor_name: str, specialty: str, hospital: str, appt_date: str,
                    appt_time: str, reason: str = "", notes: str = "") -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO appointments (user_id, doctor_name, specialty, hospital, appt_date, appt_time, reason, "
            "notes, status, created_at) VALUES (?,?,?,?,?,?,?,?, 'scheduled', ?)",
            (user_id, doctor_name, specialty, hospital, appt_date, appt_time, reason, notes, _now()))
        return cur.lastrowid


def get_appointments(user_id: int) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM appointments WHERE user_id = ? ORDER BY appt_date, appt_time",
                            (user_id,)).fetchall()
        return [dict(r) for r in rows]


def update_appointment_status(user_id: int, appt_id: int, status: str):
    with get_conn() as conn:
        conn.execute("UPDATE appointments SET status = ? WHERE id = ? AND user_id = ?", (status, appt_id, user_id))


# ======================= Emergency card =======================
def upsert_emergency_card(user_id: int, data: dict, public_enabled: bool, regenerate_token: bool = False):
    existing = get_emergency_card(user_id)
    token = (existing or {}).get("token")
    if not token or regenerate_token:
        token = secrets.token_urlsafe(12)
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO emergency_cards (user_id, data, token, public_enabled, updated_at) VALUES (?,?,?,?,?) "
            "ON CONFLICT(user_id) DO UPDATE SET data=excluded.data, token=excluded.token, "
            "public_enabled=excluded.public_enabled, updated_at=excluded.updated_at",
            (user_id, json.dumps(data), token, int(public_enabled), _now()))
    return token


def _parse_card(row) -> dict | None:
    if not row:
        return None
    d = dict(row)
    d["data"] = json.loads(d["data"] or "{}")
    d["public_enabled"] = bool(d["public_enabled"])
    return d


def get_emergency_card(user_id: int):
    with get_conn() as conn:
        return _parse_card(conn.execute("SELECT * FROM emergency_cards WHERE user_id = ?", (user_id,)).fetchone())


def get_emergency_card_by_token(token: str):
    """Only returns a card whose owner enabled public access."""
    if not token:
        return None
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM emergency_cards WHERE token = ? AND public_enabled = 1",
                           (token,)).fetchone()
        card = _parse_card(row)
        if card:
            u = conn.execute("SELECT name FROM users WHERE id = ?", (card["user_id"],)).fetchone()
            card["name"] = u["name"] if u else ""
        return card


# ======================= Imported doctor directory =======================
def replace_imported_doctors(rows: list[dict]):
    with get_conn() as conn:
        conn.execute("DELETE FROM doctors_imported")
        for r in rows:
            conn.execute(
                "INSERT INTO doctors_imported (name, specialty, district, hospital, lat, lon, rating, "
                "years_experience, consultation_fee_inr, phone, imported_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (r["name"], r["specialty"], r["district"], r["hospital"], r["lat"], r["lon"], r["rating"],
                 r["years_experience"], r["consultation_fee_inr"], r["phone"], _now()))


def get_imported_doctors() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM doctors_imported ORDER BY id").fetchall()
        return [dict(r) | {"is_demo_data": False} for r in rows]


def clear_imported_doctors():
    with get_conn() as conn:
        conn.execute("DELETE FROM doctors_imported")


# ======================= Admin / export / delete =======================
def get_admin_stats() -> dict:
    tables = {"story_entries": "Story entries", "tracker_entries": "Tracker check-ins", "reports": "Reports",
              "insights": "Insights", "chat_messages": "Chat messages", "appointments": "Appointments",
              "medicines": "Medicines", "vitals": "Vitals readings", "feedback": "Feedback items"}
    with get_conn() as conn:
        stats = {label: conn.execute(f"SELECT COUNT(*) c FROM {t}").fetchone()["c"] for t, label in tables.items()}
        stats["Accounts"] = conn.execute("SELECT COUNT(*) c FROM users WHERE owner_id IS NULL").fetchone()["c"]
        stats["Family profiles"] = conn.execute("SELECT COUNT(*) c FROM users WHERE owner_id IS NOT NULL").fetchone()["c"]
        signups = conn.execute("SELECT substr(created_at,1,10) d, COUNT(*) c FROM users WHERE owner_id IS NULL "
                               "GROUP BY d ORDER BY d").fetchall()
        stats["signups_by_day"] = [dict(r) for r in signups]
        stats["avg_rating"] = conn.execute("SELECT AVG(rating) a FROM feedback WHERE rating IS NOT NULL").fetchone()["a"]
        return stats


def list_accounts() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("SELECT id, name, email, created_at FROM users WHERE owner_id IS NULL ORDER BY id").fetchall()
        return [dict(r) for r in rows]


def first_account_id() -> int | None:
    with get_conn() as conn:
        row = conn.execute("SELECT MIN(id) m FROM users WHERE owner_id IS NULL").fetchone()
        return row["m"]


def export_all_data(user_id: int) -> dict:
    return {
        "story_entries": get_story_entries(user_id),
        "tracker_entries": get_tracker_range(user_id, "2000-01-01"),
        "vitals": get_vitals(user_id),
        "reports": get_reports(user_id),
        "medicines": get_medicines(user_id, active_only=False),
        "appointments": get_appointments(user_id),
        "insights": get_insights(user_id),
        "chat_messages": get_chat_history(user_id),
        "specialist_opinions": get_specialist_opinions(user_id),
    }


def delete_all_user_data(user_id: int):
    """Deletes the profile and everything tied to it (and any family members it owns)."""
    for m in get_members(user_id):
        delete_all_user_data(m["id"])
    with get_conn() as conn:
        for t in DATA_TABLES:
            conn.execute(f"DELETE FROM {t} WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
