"""Vitals classification (BMI / BP / blood sugar) and the cross-source risk-flag engine.

Everything here is worded as 'in / above / below the usual target range' and 'worth discussing
with your clinician': never as a diagnosis."""
from datetime import date, timedelta

import db
import labs
from specialties import SPECIALTIES

TARGETS = [
    ("BMI", "18.5 – 24.9 kg/m²", "Underweight < 18.5 · Overweight 25 – 29.9 · Obese ≥ 30 (WHO adult categories)"),
    ("Blood pressure", "< 120 / 80 mmHg", "Elevated 120 – 129 / <80 · Stage 1: 130 – 139 or 80 – 89 · Stage 2: ≥ 140 or ≥ 90"),
    ("Fasting sugar", "70 – 99 mg/dL", "100 – 125 is above the usual target · ≥ 126 is in the range clinicians follow up"),
    ("Post-meal sugar (2 h)", "< 140 mg/dL", "140 – 199 above target · ≥ 200 high"),
]


def bmi(weight_kg, height_cm):
    if not weight_kg or not height_cm:
        return None, None
    value = round(weight_kg / ((height_cm / 100) ** 2), 1)
    if value < 18.5:
        return value, ("Below target range", "watch")
    if value < 25:
        return value, ("In target range", "ok")
    if value < 30:
        return value, ("Above target range", "watch")
    return value, ("Well above target range", "alert")


def bp_category(systolic, diastolic):
    if not systolic or not diastolic:
        return None
    if systolic > 180 or diastolic > 120:
        return ("Very high, seek medical help now", "alert")
    if systolic >= 140 or diastolic >= 90:
        return ("Stage 2 range", "alert")
    if systolic >= 130 or diastolic >= 80:
        return ("Stage 1 range", "watch")
    if systolic >= 120:
        return ("Elevated", "watch")
    if systolic < 90 or diastolic < 60:
        return ("Below usual range", "watch")
    return ("In target range", "ok")


def fasting_sugar_category(v):
    if v is None:
        return None
    if v < 70:
        return ("Below target range", "alert")
    if v < 100:
        return ("In target range", "ok")
    if v < 126:
        return ("Above target range", "watch")
    return ("High, worth clinical follow-up", "alert")


def postmeal_sugar_category(v):
    if v is None:
        return None
    if v < 140:
        return ("In target range", "ok")
    if v < 200:
        return ("Above target range", "watch")
    return ("High, worth clinical follow-up", "alert")


def adherence(user_id: int, days: int = 7, today: date | None = None) -> tuple[int, int]:
    """(doses taken, doses expected) over the last `days` days for active medicines."""
    today = today or date.today()
    window_start = today - timedelta(days=days - 1)
    expected = 0
    for m in db.get_medicines(user_id):
        start = date.fromisoformat(m["start_date"]) if m.get("start_date") else window_start
        end = date.fromisoformat(m["end_date"]) if m.get("end_date") else today
        d0, d1 = max(start, window_start), min(end, today)
        if d1 >= d0:
            expected += ((d1 - d0).days + 1) * len(m["slots"])
    logs = db.get_dose_logs(user_id, window_start.isoformat())
    taken = sum(1 for l in logs if l["taken"] and l["log_date"] <= today.isoformat())
    return taken, expected


def _avg(values):
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else None


def compute_risk_flags(user_id: int, today: date | None = None) -> list[dict]:
    """Cross-source discussion points. Each: {level: watch|discuss, title, detail, sources}."""
    today = today or date.today()
    flags = []

    def add(level, title, detail, sources):
        flags.append({"level": level, "title": title, "detail": detail, "sources": sources})

    week = db.get_tracker_range(user_id, (today - timedelta(days=6)).isoformat())
    sleep = [e["sleep_hours"] for e in week if e.get("sleep_hours") is not None]
    stress_avg, energy_avg = _avg([e.get("stress_level") for e in week]), _avg([e.get("energy_level") for e in week])
    sleep_avg = _avg(sleep)
    pain_days = sum(1 for e in week[-5:] if (e.get("pain_level") or 0) >= 7)
    pain_avg = _avg([e.get("pain_level") for e in week])

    if len(sleep) >= 3 and sleep_avg < 6:
        add("watch", "Short-sleep pattern", f"You averaged {sleep_avg:.1f} h of sleep over the last {len(sleep)} logged days.", ["tracker"])
    if pain_days >= 2:
        add("discuss", "Repeated high pain days", f"Pain was rated 7 or higher on {pain_days} of your last 5 check-ins.", ["tracker"])
    if stress_avg is not None and len(week) >= 3 and stress_avg >= 8:
        add("watch", "Sustained high stress", f"Average stress {stress_avg:.1f}/10 this week.", ["tracker"])
    if energy_avg is not None and len(week) >= 3 and energy_avg <= 3:
        add("watch", "Persistently low energy", f"Average energy {energy_avg:.1f}/10 this week.", ["tracker"])

    vitals = db.get_vitals(user_id)
    latest_bp = next(((v["systolic"], v["diastolic"]) for v in reversed(vitals) if v.get("systolic") and v.get("diastolic")), None)
    bp_cat = bp_category(*latest_bp) if latest_bp else None
    if bp_cat and bp_cat[1] in ("alert",):
        add("discuss", "Blood pressure above usual target", f"Latest reading {latest_bp[0]}/{latest_bp[1]} mmHg ({bp_cat[0]}).", ["vitals"])
    fs = next((v["fasting_sugar"] for v in reversed(vitals) if v.get("fasting_sugar")), None)
    fs_cat = fasting_sugar_category(fs)
    if fs_cat and fs_cat[1] != "ok":
        add("discuss" if fs_cat[1] == "alert" else "watch", "Fasting sugar outside target", f"Latest fasting value {fs:g} mg/dL ({fs_cat[0]}).", ["vitals"])
    w = next(((v["weight_kg"], v["height_cm"]) for v in reversed(vitals) if v.get("weight_kg") and v.get("height_cm")), None)
    if w:
        b, cat = bmi(*w)
        if cat[1] != "ok":
            add("watch", "BMI outside target range", f"BMI {b} ({cat[0]}).", ["vitals"])

    abnormal = labs.latest_abnormal(labs.build_lab_series(db.get_reports(user_id)))
    if abnormal:
        names = ", ".join(sorted({a["label"] for a in abnormal})[:5])
        add("discuss" if len(abnormal) >= 2 else "watch", "Lab values outside reference range",
            f"{len(abnormal)} test(s) on your latest reports are out of range: {names}.", ["reports"])

    taken, expected = adherence(user_id, 7, today)
    if expected >= 5 and taken / expected < 0.6:
        add("watch", "Missed medicine doses", f"You logged {taken} of {expected} expected doses this week ({round(100*taken/expected)}%).", ["medicines"])

    chunks = db.get_evidence_chunks(user_id)
    theme_stats: dict[str, dict] = {}
    for c in chunks:
        for t in c["theme_tags"]:
            if t in SPECIALTIES:
                s = theme_stats.setdefault(t, {"n": 0, "sources": set()})
                s["n"] += 1
                s["sources"].add(c["source_type"])
    recurring = {t: s for t, s in theme_stats.items() if s["n"] >= 3 and len(s["sources"]) >= 2}
    for t, s in recurring.items():
        add("discuss", f"Recurring {t} symptoms",
            f"{s['n']} mentions across {', '.join(sorted(s['sources']))}. Consider raising this with a {t} specialist.", sorted(s["sources"]))

    # combined signals: a symptom pattern backed by a matching measurement
    if "Cardiology" in recurring and bp_cat and bp_cat[1] != "ok":
        add("discuss", "Combined signal: heart-related symptoms + blood pressure",
            "Recurring cardiology-type symptoms appear alongside a blood pressure reading outside the usual target.", ["story/survey", "vitals"])
    if "Psychiatry / Mental Health" in recurring and ((stress_avg or 0) >= 7 or (sleep_avg is not None and sleep_avg < 6)):
        add("discuss", "Combined signal: mood symptoms + stress/sleep",
            "Recurring mood-related symptoms appear alongside high stress or short sleep in your tracker.", ["story/survey", "tracker"])
    if "Orthopedics" in recurring and (pain_avg or 0) >= 5:
        add("discuss", "Combined signal: joint/back symptoms + pain scores",
            "Recurring musculoskeletal symptoms appear alongside consistently elevated pain scores.", ["story/survey", "tracker"])

    order = {"discuss": 0, "watch": 1}
    return sorted(flags, key=lambda f: order[f["level"]])


def symptom_gaps(user_id: int) -> list[dict]:
    """Symptom themes that keep recurring (>=2 distinct weeks or >=3 mentions) with no resolution recorded."""
    from datetime import datetime
    by_theme: dict[str, list] = {}
    for c in db.get_evidence_chunks(user_id):
        for tag in c["theme_tags"]:
            if tag != "general_wellbeing":
                by_theme.setdefault(tag, []).append(datetime.fromisoformat(c["timestamp"]))
    gaps = []
    for theme, stamps in by_theme.items():
        weeks = {(t.isocalendar()[0], t.isocalendar()[1]) for t in stamps}
        if len(weeks) >= 2 or len(stamps) >= 3:
            gaps.append({"symptom": theme, "occurrences": len(stamps), "first": min(stamps), "last": max(stamps)})
    return sorted(gaps, key=lambda g: -g["occurrences"])
