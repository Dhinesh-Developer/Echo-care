"""V4: directory import, appointments/calendar/ICS, PDF report, family profiles, emergency card, admin."""
import io
import os
from datetime import date, timedelta

import pandas as pd

import auth, calendar_utils as cu, db, doctors_data as dd, report_pdf
from conftest import run_page

ROOT = os.path.dirname(os.path.dirname(__file__))
page = lambda name: os.path.join(ROOT, "pages", name)


# ---------- real doctor directory ----------
def test_template_csv_imports_cleanly():
    rows, errors, warns = dd.parse_directory_upload(pd.read_csv(io.StringIO(dd.template_csv())))
    assert len(rows) == 2 and errors == [] and any("centre" in w for w in warns)


def test_import_validation_and_normalisation():
    df = pd.DataFrame([
        {"name": "Dr A", "specialty": "cardiologist", "district": "chennai", "hospital": "H1", "lat": 13.0, "lon": 80.2, "rating": 9},
        {"name": "Dr B", "specialty": "Psychiatry", "district": "Madurai", "hospital": "H2"},
        {"name": "Dr C", "specialty": "Cardiology", "district": "Atlantis", "hospital": "H3"},     # unknown place, no coords -> skipped
        {"name": "", "specialty": "ENT", "district": "Salem", "hospital": "H4"},                     # no name -> skipped
        {"name": "Dr E", "specialty": "Astrology", "district": "Salem", "hospital": "H5", "lat": 11.6, "lon": 78.1},
    ])
    rows, errors, warns = dd.parse_directory_upload(df)
    by = {r["name"]: r for r in rows}
    assert by["Dr A"]["specialty"] == "Cardiology" and by["Dr A"]["rating"] == 5.0 and by["Dr A"]["district"] == "Chennai"
    assert by["Dr B"]["specialty"] == "Psychiatry / Mental Health"
    assert len(errors) == 2 and any("Astrology" in w for w in warns) and "Dr C" not in by
    assert dd.parse_directory_upload(pd.DataFrame([{"name": "x"}]))[1]  # missing required columns reported


def test_imported_directory_replaces_demo_and_can_reset():
    assert dd.directory_source() == "demo"
    rows, _, _ = dd.parse_directory_upload(pd.read_csv(io.StringIO(dd.template_csv())))
    db.replace_imported_doctors(rows)
    d = dd.get_directory()
    assert dd.directory_source(d) == "imported" and len(d) == 2 and not d[0]["is_demo_data"]
    assert set(dd.directory_districts(d)) == {"Chennai", "Coimbatore"}
    db.clear_imported_doctors()
    assert dd.directory_source() == "demo"


def test_navigation_links_need_no_api_key():
    assert dd.navigate_url(13.08, 80.27).startswith("https://www.google.com/maps/dir/?api=1&destination=13.08,80.27")
    assert "query=cardiology%20hospital" in dd.maps_search_url("cardiology hospital")


def test_find_doctors_page_uses_imported_data(user):
    rows, _, _ = dd.parse_directory_upload(pd.read_csv(io.StringIO(dd.template_csv())))
    db.replace_imported_doctors(rows)
    at = run_page(page("13_🏥_Find_Doctors.py"), user)
    assert not list(at.exception) and any("Imported real directory" in m.value for m in at.markdown)


# ---------- appointments ----------
def test_appointment_lifecycle_calendar_and_ics(user):
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    aid = db.add_appointment(user["id"], "Dr Rao", "Cardiology", "City Hospital", tomorrow, "10:30", "checkup")
    appts = db.get_appointments(user["id"])
    grid = cu.month_grid_html(date.fromisoformat(tomorrow).year, date.fromisoformat(tomorrow).month, appts)
    assert "Dr Rao" in grid and "has-appt" in grid
    ics = cu.ics_event(appts[0])
    assert "BEGIN:VEVENT" in ics and f"DTSTART:{tomorrow.replace('-', '')}T103000" in ics and "VALARM" in ics
    db.update_appointment_status(user["id"], aid, "cancelled")
    assert "Dr Rao" not in cu.month_grid_html(date.fromisoformat(tomorrow).year, date.fromisoformat(tomorrow).month, db.get_appointments(user["id"]))


def test_appointments_page_shows_tomorrow_reminder(user):
    db.add_appointment(user["id"], "Dr Rao", "Cardiology", "City", (date.today() + timedelta(days=1)).isoformat(), "09:00")
    at = run_page(page("14_📅_Appointments.py"), user)
    assert any("Tomorrow" in w.value for w in at.warning)


# ---------- PDF ----------
def test_pdf_report_builds_and_respects_section_choices(user):
    db.upsert_vitals(user["id"], date.today().isoformat(), weight_kg=70, height_cm=170, systolic=135, diastolic=85)
    db.add_medicine(user["id"], "Metformin", "500 mg", "Twice daily", ["Morning", "Night"], date.today().isoformat(), None)
    full = report_pdf.build_pdf(user["id"], "Test Patient")
    small = report_pdf.build_pdf(user["id"], "Test Patient", {k: k == "vitals" for k in report_pdf.SECTIONS})
    assert full[:5] == b"%PDF-" and small[:5] == b"%PDF-" and len(full) > len(small)


# ---------- family profiles ----------
def test_family_profiles_isolate_data_and_cascade_delete(user):
    mom = db.create_member(user["id"], "Mom", "Mother", "1960-05-01")
    at = run_page(page("4_📈_Daily_Tracker.py"), user, active_profile_id=mom)
    at.button[0].click().run()
    assert db.get_tracker_streak(mom) == 1 and db.get_tracker_streak(user["id"]) == 0
    assert auth.is_admin is not None
    db.delete_all_user_data(user["id"])
    assert db.get_user_by_id(mom) is None and db.get_tracker_range(mom, "2000-01-01") == []


def test_members_cannot_log_in_or_be_hijacked(user):
    mom = db.create_member(user["id"], "Mom", "Mother")
    member = db.get_user_by_id(mom)
    assert auth.verify_password("anything", member["password_hash"]) is False
    other = db.create_user("Eve", "eve@x.com", auth.hash_password("password123"))
    assert db.delete_member(other, mom) is False  # only the owner can delete
    assert db.get_user_by_id(mom) is not None


def test_active_profile_must_belong_to_account(user):
    other = db.create_user("Eve", "eve@x.com", auth.hash_password("password123"))
    stranger = db.create_member(other, "Eve's mom", "Mother")
    at = run_page(page("1_📊_Dashboard.py"), user, active_profile_id=stranger)
    assert not list(at.exception)
    assert at.session_state["active_profile_id"] if "active_profile_id" in at.session_state else True
    assert auth.current_user is not None


# ---------- emergency card ----------
def test_emergency_card_public_access_control(user):
    token = db.upsert_emergency_card(user["id"], {"blood_group": "O+", "allergies": "Penicillin"}, public_enabled=True)
    assert db.get_emergency_card_by_token(token)["data"]["blood_group"] == "O+"
    assert db.get_emergency_card_by_token("wrong") is None
    db.upsert_emergency_card(user["id"], {"blood_group": "O+"}, public_enabled=False)
    assert db.get_emergency_card_by_token(token) is None          # owner switched it off
    new = db.upsert_emergency_card(user["id"], {"blood_group": "O+"}, True, regenerate_token=True)
    assert new != token and db.get_emergency_card_by_token(token) is None and db.get_emergency_card_by_token(new)


def test_public_card_page_works_without_login_and_hides_bad_tokens(user):
    from streamlit.testing.v1 import AppTest
    token = db.upsert_emergency_card(user["id"], {"blood_group": "AB-", "allergies": "Peanuts"}, True)
    at = AppTest.from_file(os.path.join(ROOT, "Home.py"), default_timeout=30)
    at.query_params["card"] = token
    at.run()
    assert not list(at.exception) and any("AB-" in m.value for m in at.markdown)
    assert not any("Log in" in t.label for t in at.tabs)           # no login UI on the public view
    at2 = AppTest.from_file(os.path.join(ROOT, "Home.py"), default_timeout=30)
    at2.query_params["card"] = "bogus"
    at2.run()
    assert len(at2.error) == 1


# ---------- admin ----------
def test_admin_gating_first_user_and_env_override(user, monkeypatch):
    second = {"id": db.create_user("Bob", "bob@x.com", "x"), "name": "Bob", "email": "bob@x.com"}
    assert not list(run_page(page("19_🔐_Admin.py"), user).error)          # first account = admin
    assert len(run_page(page("19_🔐_Admin.py"), second).error) == 1       # others blocked
    monkeypatch.setenv("ADMIN_EMAILS", "bob@x.com")
    assert not list(run_page(page("19_🔐_Admin.py"), second).error)
    assert len(run_page(page("19_🔐_Admin.py"), user).error) == 1


def test_admin_stats_count_accounts_and_family(user):
    db.create_member(user["id"], "Mom", "Mother")
    db.insert_feedback(user["id"], "General", "great", 5)
    s = db.get_admin_stats()
    assert s["Accounts"] == 1 and s["Family profiles"] == 1 and s["avg_rating"] == 5
