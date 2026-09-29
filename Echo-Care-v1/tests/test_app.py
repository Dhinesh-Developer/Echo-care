"""
Automated regression tests using Streamlit's own AppTest framework — actually
executes each page's script (not just a syntax check) and asserts on both
the absence of exceptions and real app behavior (data saved, emergency guard
firing, evidence-gate thresholds respected).

Run: pytest tests/ -v   (from the project root)
"""
import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from streamlit.testing.v1 import AppTest

import db
import auth
import rag

PAGES = [
    "app.py",
    "pages/1_📊_Dashboard.py",
    "pages/2_📖_My_Story.py",
    "pages/3_📋_Health_Survey.py",
    "pages/4_📊_Daily_Tracker.py",
    "pages/5_📄_Medical_Reports.py",
    "pages/6_✨_AI_Insights.py",
    "pages/7_💬_Echo_Companion.py",
    "pages/8_🛡️_Diagnostic_Guard.py",
    "pages/9_🏥_Find_Doctors.py",
    "pages/10_🧘_Wellness.py",
    "pages/11_⚙️_Settings.py",
]


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Point db.py at a throwaway sqlite file per test so tests never collide."""
    test_db_path = str(tmp_path / "test_echocare.db")
    monkeypatch.setattr(db, "DB_PATH", test_db_path)
    db.init_db()
    yield


@pytest.fixture
def test_user():
    user_id = db.create_user("Test Patient", "patient@test.com", auth.hash_password("password123"))
    return {"id": user_id, "name": "Test Patient", "email": "patient@test.com"}


@pytest.mark.parametrize("page", PAGES)
def test_page_renders_without_exception(page, test_user):
    at = AppTest.from_file(page)
    at.session_state["user"] = test_user
    at.run(timeout=30)
    assert not list(at.exception), f"{page} raised: {list(at.exception)}"


def test_logged_out_user_is_blocked_from_protected_pages():
    at = AppTest.from_file("pages/1_📊_Dashboard.py")
    at.run(timeout=30)
    assert not list(at.exception)
    assert any("log in" in w.value.lower() or "log in" in str(w).lower() for w in at.warning) or len(at.warning) > 0


def test_story_entry_tagged_correctly(test_user):
    at = AppTest.from_file("pages/2_📖_My_Story.py")
    at.session_state["user"] = test_user
    at.run(timeout=30)
    at.text_area[0].set_value("I've had a persistent cough and wheezing for a week.")
    at.button[0].click().run(timeout=30)

    entries = db.get_story_entries(test_user["id"])
    assert len(entries) == 1
    assert "Pulmonology" in entries[0]["extracted_symptoms"]


def test_emergency_language_blocks_story_storage(test_user):
    at = AppTest.from_file("pages/2_📖_My_Story.py")
    at.session_state["user"] = test_user
    at.run(timeout=30)
    at.text_area[0].set_value("I have severe chest pain and can't breathe right now.")
    at.button[0].click().run(timeout=30)

    assert len(at.error) > 0  # emergency resources shown
    assert len(db.get_story_entries(test_user["id"])) == 0  # never stored as a normal entry


def test_tracker_streak_increments(test_user):
    at = AppTest.from_file("pages/4_📊_Daily_Tracker.py")
    at.session_state["user"] = test_user
    at.run(timeout=30)
    at.button[0].click().run(timeout=30)
    assert db.get_tracker_streak(test_user["id"]) == 1


def test_insight_gated_until_evidence_sufficient(test_user):
    # Below the sufficiency gate (only 1 occurrence, 1 source type): no insight
    rag.chunk_and_store(test_user["id"], "narrative", "I have joint pain in my knee.", {})
    insights = rag.generate_insights(test_user["id"], lambda p: {"ok": False, "text": None, "provider": "none"})
    assert insights == []

    # Now cross the gate: 2+ occurrences across 2+ source types
    rag.chunk_and_store(test_user["id"], "survey", "Knee joint pain also noted in survey.", {})
    insights = rag.generate_insights(test_user["id"], lambda p: {"ok": False, "text": None, "provider": "none"})
    assert len(insights) >= 1
    assert insights[0]["generated_by"] == "unavailable"  # honest fallback, no fake text


def test_department_classifier_returns_valid_specialty():
    from department_classifier import predict_department
    from specialties import ALL_SPECIALTIES
    result = predict_department("chest pain and palpitations when climbing stairs")
    assert result["top_department"] in ALL_SPECIALTIES


def test_doctor_directory_covers_all_specialties_and_districts():
    import doctors_data as dd
    from specialties import ALL_SPECIALTIES
    found_specialties = {d["specialty"] for d in dd.DOCTORS}
    found_districts = {d["district"] for d in dd.DOCTORS}
    assert found_specialties == set(ALL_SPECIALTIES)
    assert found_districts == set(dd.DISTRICTS.keys())
    assert all(d["is_demo_data"] for d in dd.DOCTORS)
