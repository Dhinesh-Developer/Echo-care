"""
SQLite persistence layer. Chosen over MongoDB/Postgres so the entire project
runs from a single `streamlit run app.py` with zero external services —
matching the "deploy through Streamlit only" requirement.

NOTE on Streamlit Community Cloud: the filesystem is ephemeral and resets on
redeploy/sleep. For a class demo or local run this is fine (data persists
across the session and across reruns on the same machine). For a persistent
production deployment, swap the sqlite3 connection below for a hosted
Postgres/Supabase connection string — every function in this file is the only
place that would need to change.
"""
import sqlite3
import json
import os
from contextlib import contextmanager
from datetime import datetime, date

DB_PATH = os.path.join(os.path.dirname(__file__), "echocare.db")


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


def init_db():
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS evidence_chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                source_type TEXT NOT NULL,
                text TEXT NOT NULL,
                theme_tags TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                metadata TEXT
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS story_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                text TEXT NOT NULL,
                extracted_symptoms TEXT NOT NULL,
                timeline TEXT,
                created_at TEXT NOT NULL
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS survey_responses (
                user_id INTEGER PRIMARY KEY,
                about_you TEXT, main_concern TEXT, care_context TEXT,
                step_complete INTEGER DEFAULT 0, updated_at TEXT
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS tracker_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                entry_date TEXT NOT NULL,
                sleep_hours REAL, water_glasses INTEGER, stress_level INTEGER,
                energy_level INTEGER, pain_level INTEGER, notes TEXT,
                updated_at TEXT,
                UNIQUE(user_id, entry_date)
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                filename TEXT, extraction_method TEXT,
                raw_text_excerpt TEXT, fields TEXT, created_at TEXT
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS insights (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                theme TEXT, text TEXT, confidence REAL, confidence_label TEXT,
                evidence_summary TEXT, evidence_chunk_ids TEXT,
                generated_by TEXT, created_at TEXT
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                role TEXT NOT NULL, content TEXT NOT NULL,
                is_emergency INTEGER DEFAULT 0, created_at TEXT
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS specialist_opinions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                specialist_name TEXT, department TEXT, opinion_text TEXT, created_at TEXT
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                context TEXT, outcome TEXT, rating INTEGER, created_at TEXT
            )
        """)


# ---------------- Users ----------------
def create_user(name: str, email: str, password_hash: str) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO users (name, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
            (name, email, password_hash, datetime.utcnow().isoformat()),
        )
        return cur.lastrowid


def get_user_by_email(email: str):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        return dict(row) if row else None


# ---------------- Evidence chunks (LE-RAG) ----------------
def insert_evidence_chunk(user_id: int, source_type: str, text: str, theme_tags: list, metadata: dict | None = None):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO evidence_chunks (user_id, source_type, text, theme_tags, timestamp, metadata) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, source_type, text, json.dumps(theme_tags), datetime.utcnow().isoformat(),
             json.dumps(metadata or {})),
        )


def get_evidence_chunks(user_id: int) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM evidence_chunks WHERE user_id = ?", (user_id,)).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["theme_tags"] = json.loads(d["theme_tags"])
            d["metadata"] = json.loads(d["metadata"] or "{}")
            out.append(d)
        return out


# ---------------- Story ----------------
def insert_story_entry(user_id: int, text: str, symptoms: list, timeline: str | None):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO story_entries (user_id, text, extracted_symptoms, timeline, created_at) VALUES (?, ?, ?, ?, ?)",
            (user_id, text, json.dumps(symptoms), timeline, datetime.utcnow().isoformat()),
        )


def get_story_entries(user_id: int) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM story_entries WHERE user_id = ? ORDER BY created_at DESC", (user_id,)
        ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["extracted_symptoms"] = json.loads(d["extracted_symptoms"])
            out.append(d)
        return out


# ---------------- Survey ----------------
def upsert_survey(user_id: int, about_you: dict, main_concern: dict, care_context: dict, step_complete: int):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO survey_responses (user_id, about_you, main_concern, care_context, step_complete, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET about_you=excluded.about_you, main_concern=excluded.main_concern, "
            "care_context=excluded.care_context, step_complete=excluded.step_complete, updated_at=excluded.updated_at",
            (user_id, json.dumps(about_you), json.dumps(main_concern), json.dumps(care_context),
             step_complete, datetime.utcnow().isoformat()),
        )


def get_survey(user_id: int):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM survey_responses WHERE user_id = ?", (user_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["about_you"] = json.loads(d["about_you"] or "{}")
        d["main_concern"] = json.loads(d["main_concern"] or "{}")
        d["care_context"] = json.loads(d["care_context"] or "{}")
        return d


# ---------------- Tracker ----------------
def upsert_tracker_entry(user_id: int, entry_date: str, **fields):
    cols = ["sleep_hours", "water_glasses", "stress_level", "energy_level", "pain_level", "notes"]
    values = [fields.get(c) for c in cols]
    with get_conn() as conn:
        conn.execute(
            f"INSERT INTO tracker_entries (user_id, entry_date, {', '.join(cols)}, updated_at) "
            f"VALUES (?, ?, {', '.join(['?'] * len(cols))}, ?) "
            f"ON CONFLICT(user_id, entry_date) DO UPDATE SET "
            + ", ".join(f"{c}=excluded.{c}" for c in cols) + ", updated_at=excluded.updated_at",
            (user_id, entry_date, *values, datetime.utcnow().isoformat()),
        )


def get_tracker_entry(user_id: int, entry_date: str):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM tracker_entries WHERE user_id = ? AND entry_date = ?", (user_id, entry_date)
        ).fetchone()
        return dict(row) if row else None


def get_tracker_range(user_id: int, start_date: str) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM tracker_entries WHERE user_id = ? AND entry_date >= ? ORDER BY entry_date ASC",
            (user_id, start_date),
        ).fetchall()
        return [dict(r) for r in rows]


def get_tracker_streak(user_id: int) -> int:
    from datetime import timedelta
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT entry_date FROM tracker_entries WHERE user_id = ? ORDER BY entry_date DESC", (user_id,)
        ).fetchall()
    dates = {r["entry_date"] for r in rows}
    streak, cursor = 0, date.today()
    while cursor.isoformat() in dates:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


# ---------------- Reports ----------------
def insert_report(user_id: int, filename: str, extraction_method: str, raw_text_excerpt: str, fields: list):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO reports (user_id, filename, extraction_method, raw_text_excerpt, fields, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, filename, extraction_method, raw_text_excerpt, json.dumps(fields), datetime.utcnow().isoformat()),
        )


def get_reports(user_id: int) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM reports WHERE user_id = ? ORDER BY created_at DESC", (user_id,)).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["fields"] = json.loads(d["fields"])
            out.append(d)
        return out


# ---------------- Insights ----------------
def insert_insight(user_id: int, insight: dict):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO insights (user_id, theme, text, confidence, confidence_label, evidence_summary, "
            "evidence_chunk_ids, generated_by, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (user_id, insight["theme"], insight["text"], insight["confidence"], insight["confidence_label"],
             insight["evidence_summary"], json.dumps(insight["evidence_chunk_ids"]), insight["generated_by"],
             datetime.utcnow().isoformat()),
        )


def get_insights(user_id: int) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM insights WHERE user_id = ? ORDER BY created_at DESC", (user_id,)
        ).fetchall()
        return [dict(r) for r in rows]


# ---------------- Chat ----------------
def insert_chat_message(user_id: int, role: str, content: str, is_emergency: bool = False):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO chat_messages (user_id, role, content, is_emergency, created_at) VALUES (?, ?, ?, ?, ?)",
            (user_id, role, content, int(is_emergency), datetime.utcnow().isoformat()),
        )


def get_chat_history(user_id: int) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM chat_messages WHERE user_id = ? ORDER BY created_at ASC", (user_id,)
        ).fetchall()
        return [dict(r) for r in rows]


# ---------------- Diagnostic Guard ----------------
def insert_specialist_opinion(user_id: int, specialist_name: str, department: str, opinion_text: str):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO specialist_opinions (user_id, specialist_name, department, opinion_text, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, specialist_name, department, opinion_text, datetime.utcnow().isoformat()),
        )


def get_specialist_opinions(user_id: int) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM specialist_opinions WHERE user_id = ?", (user_id,)).fetchall()
        return [dict(r) for r in rows]


# ---------------- Feedback ----------------
def insert_feedback(user_id: int, context: str, outcome: str, rating: int):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO feedback (user_id, context, outcome, rating, created_at) VALUES (?, ?, ?, ?, ?)",
            (user_id, context, outcome, rating, datetime.utcnow().isoformat()),
        )


def export_all_data(user_id: int) -> dict:
    return {
        "story_entries": get_story_entries(user_id),
        "tracker_entries": get_tracker_range(user_id, "2000-01-01"),
        "reports": get_reports(user_id),
        "insights": get_insights(user_id),
        "chat_messages": get_chat_history(user_id),
        "specialist_opinions": get_specialist_opinions(user_id),
    }


def delete_all_user_data(user_id: int):
    tables = ["evidence_chunks", "story_entries", "survey_responses", "tracker_entries",
              "reports", "insights", "chat_messages", "specialist_opinions", "feedback"]
    with get_conn() as conn:
        for t in tables:
            id_col = "user_id"
            conn.execute(f"DELETE FROM {t} WHERE {id_col} = ?", (user_id,))
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
