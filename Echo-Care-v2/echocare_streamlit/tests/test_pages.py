"""Every page is EXECUTED (not just imported) with seeded data, plus core V1 behaviours."""
import glob
import os
from datetime import date, timedelta

import pytest

import db, rag
from conftest import run_page

ROOT = os.path.dirname(os.path.dirname(__file__))
PAGES = ["Home.py"] + sorted(glob.glob(os.path.join(ROOT, "pages", "*.py")),
                            key=lambda p: int(os.path.basename(p).split("_")[0]))


def seed(uid):
    for i in range(5):
        d = (date.today() - timedelta(days=i)).isoformat()
        db.upsert_tracker_entry(uid, d, sleep_hours=5, stress_level=8, energy_level=3, pain_level=7, notes="knee joint pain")
        db.upsert_vitals(uid, d, weight_kg=72, height_cm=170, systolic=138, diastolic=88, fasting_sugar=112)
    for txt, src in [("Chest tightness and palpitations on stairs.", "narrative"), ("Racing heartbeat.", "survey"), ("Palpitations at night.", "tracker")]:
        rag.chunk_and_store(uid, src, txt)
    db.insert_report(uid, "a.pdf", "manual", "x", [{"test": "Hemoglobin", "value": "10.5", "unit": "g/dL", "reference_range": "12-15.5", "out_of_range": True}], "2026-08-01")
    db.add_medicine(uid, "Metformin", "500 mg", "Twice daily", ["Morning", "Night"], date.today().isoformat(), None)
    db.add_appointment(uid, "Dr Test", "Cardiology", "City", (date.today() + timedelta(days=1)).isoformat(), "10:00")
    db.insert_specialist_opinion(uid, "A", "Cardio", "The chest pain is cardiac and needs a stent")
    db.insert_specialist_opinion(uid, "B", "Ortho", "The chest pain is not cardiac, it is muscle strain")
    for ins in rag.generate_insights(uid, lambda p: {"ok": False, "text": None, "provider": "x"}):
        db.insert_insight(uid, ins)


@pytest.mark.parametrize("page", PAGES, ids=[os.path.basename(p) for p in PAGES])
def test_every_page_renders(page, user):
    seed(user["id"])
    at = run_page(page, user)
    assert not list(at.exception), [e.value for e in at.exception]
    stray = [e.value for e in at.error if "Possible conflict" not in e.value]  # the guard's intended alert on seeded data
    assert not stray, stray  # e.g. a 'No secrets found' box


def test_protected_pages_block_logged_out_users():
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(os.path.join(ROOT, "pages", "1_📊_Dashboard.py"), default_timeout=30).run()
    assert not list(at.exception) and len(at.warning) > 0


def test_story_saved_tagged_and_emergency_blocked(user):
    page = os.path.join(ROOT, "pages", "2_📖_My_Story.py")
    at = run_page(page, user)
    at.text_area[0].set_value("Persistent cough and wheezing for a week.")
    at.button[0].click().run()
    e = db.get_story_entries(user["id"])
    assert len(e) == 1 and "Pulmonology" in e[0]["extracted_symptoms"] and e[0]["timeline"]

    at = run_page(page, user)
    at.text_area[0].set_value("I have severe chest pain and can't breathe.")
    at.button[0].click().run()
    assert any("emergency" in e.value.lower() for e in at.error) and len(db.get_story_entries(user["id"])) == 1


def test_tracker_streak(user):
    at = run_page(os.path.join(ROOT, "pages", "4_📈_Daily_Tracker.py"), user)
    at.button[0].click().run()
    assert db.get_tracker_streak(user["id"]) == 1


def test_vitals_form_saves_and_classifies(user):
    at = run_page(os.path.join(ROOT, "pages", "5_💓_Vitals.py"), user)
    nums = {n.label: n for n in at.number_input}
    nums["Weight (kg)"].set_value(70.0)
    nums["Height (cm)"].set_value(170.0)
    nums["Systolic BP (mmHg)"].set_value(135)
    nums["Diastolic BP (mmHg)"].set_value(85)
    at.button[0].click().run()
    v = db.get_vitals(user["id"])
    assert len(v) == 1 and v[0]["systolic"] == 135 and v[0]["weight_kg"] == 70.0
    assert any(c["source_type"] == "vitals" for c in db.get_evidence_chunks(user["id"]))
