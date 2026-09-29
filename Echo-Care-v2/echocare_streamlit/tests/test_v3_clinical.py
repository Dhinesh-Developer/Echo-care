"""V3: lab trends, medicines, vitals rules, risk flags, symptom gaps, opinion comparison."""
from datetime import date, timedelta

import compare, db, health_rules as hr, labs, rag


def test_reference_range_parsing_and_direction():
    assert labs.parse_ref_range("12.0 – 15.5") == (12.0, 15.5)
    assert labs.parse_ref_range("<200") == (None, 200.0)
    assert labs.direction("250", "<200") == "high" and labs.direction("11", "12-15") == "low" and labs.direction("13", "12-15") == "normal"
    assert labs.direction("5", None) is None


def test_lab_series_trend_and_alerts(user):
    for d, v in [("2026-07-01", "10.0"), ("2026-08-01", "10.8"), ("2026-09-01", "12.5")]:
        db.insert_report(user["id"], "r", "manual", "", [{"test": "Hemoglobin", "value": v, "unit": "g/dL", "reference_range": "12-15.5", "out_of_range": labs.is_out_of_range(v, "12-15.5")}], d)
    db.insert_report(user["id"], "r", "manual", "", [{"test": "LDL", "value": "160", "unit": "mg/dL", "reference_range": "<100", "out_of_range": True}], "2026-09-02")
    series = labs.build_lab_series(db.get_reports(user["id"]))
    assert [p["value"] for p in series["hemoglobin"]] == [10.0, 10.8, 12.5]
    alerts = labs.latest_abnormal(series)
    assert [a["label"] for a in alerts] == ["LDL"]  # hemoglobin's latest value is back in range
    assert alerts[0]["direction"] == "high"


def test_text_extraction_regex_finds_fields():
    fields = labs.extract_fields("Hemoglobin 10.5 g/dL (12.0-15.5)")
    assert fields and fields[0]["out_of_range"] is True


def test_bmi_bp_sugar_categories():
    assert hr.bmi(70, 170) == (24.2, ("In target range", "ok"))
    assert hr.bmi(95, 170)[1][1] == "alert"
    assert hr.bp_category(118, 76)[1] == "ok" and hr.bp_category(135, 85)[1] == "watch"
    assert hr.bp_category(150, 95)[1] == "alert" and "seek medical help" in hr.bp_category(190, 100)[0]
    assert hr.fasting_sugar_category(90)[1] == "ok" and hr.fasting_sugar_category(130)[1] == "alert"
    assert hr.postmeal_sugar_category(150)[1] == "watch"


def test_medicine_adherence(user):
    start = (date.today() - timedelta(days=2)).isoformat()
    mid = db.add_medicine(user["id"], "Metformin", "500", "Twice daily", ["Morning", "Night"], start, None)
    taken, expected = hr.adherence(user["id"])
    assert (taken, expected) == (0, 6)  # 3 days x 2 slots
    db.log_dose(user["id"], mid, date.today().isoformat(), "Morning", True)
    db.log_dose(user["id"], mid, date.today().isoformat(), "Morning", True)  # idempotent upsert
    assert hr.adherence(user["id"]) == (1, 6)


def test_risk_flags_combine_sources(user):
    for i in range(5):
        d = (date.today() - timedelta(days=i)).isoformat()
        db.upsert_tracker_entry(user["id"], d, sleep_hours=4.5, stress_level=9, energy_level=2, pain_level=8)
    db.upsert_vitals(user["id"], date.today().isoformat(), systolic=150, diastolic=96, fasting_sugar=135, weight_kg=95, height_cm=170)
    for txt, src in [("Chest tightness and palpitations.", "narrative"), ("Racing heartbeat.", "survey"), ("Palpitations again.", "tracker")]:
        rag.chunk_and_store(user["id"], src, txt)
    titles = " | ".join(f["title"] for f in hr.compute_risk_flags(user["id"]))
    for expected in ("Short-sleep pattern", "Repeated high pain days", "Blood pressure above usual target",
                     "Fasting sugar outside target", "Recurring Cardiology symptoms", "Combined signal: heart-related symptoms"):
        assert expected in titles, expected
    assert "diagnos" not in " ".join(f["detail"].lower() for f in hr.compute_risk_flags(user["id"])).replace("not a diagnos", "")


def test_no_flags_when_healthy(user):
    db.upsert_tracker_entry(user["id"], date.today().isoformat(), sleep_hours=8, stress_level=3, energy_level=8, pain_level=0)
    db.upsert_vitals(user["id"], date.today().isoformat(), systolic=115, diastolic=75, fasting_sugar=88, weight_kg=68, height_cm=170)
    assert hr.compute_risk_flags(user["id"]) == []


def test_symptom_gaps(user):
    for i in range(3):
        rag.chunk_and_store(user["id"], "narrative", f"Migraine attack number {i}.")
    assert any(g["symptom"] == "Neurology" for g in hr.symptom_gaps(user["id"]))


def test_opinion_comparison_flags_conflict_and_highlights():
    a, b = "The chest pain is cardiac and needs a stent", "The chest pain is not cardiac, it is muscle strain"
    ha, hb = compare.diff_html(a, b)
    assert "ec-diff-a" in ha and "ec-diff-b" in hb
    assert compare.conflict_signals(a, b)["possible_conflict"] is True
    assert compare.conflict_signals("Rest and fluids advised", "Rest and fluids advised")["possible_conflict"] is False
