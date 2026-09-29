"""One-click PDF consultation report (reportlab). Everything is the patient's own recorded data,
organised for a clinician: never a diagnosis."""
import io
import os
from datetime import date, timedelta
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

import db
import health_rules as hr
import labs

HERE = os.path.dirname(__file__)
BLUE = colors.HexColor("#2563EB")
SLATE = colors.HexColor("#64748B")
LINE = colors.HexColor("#E2E8F0")

SECTIONS = {
    "survey": "Survey summary", "story": "Recent story entries", "tracker": "30-day tracker averages",
    "vitals": "Vitals (BMI, BP, sugar)", "labs": "Lab values outside range", "medicines": "Current medicines",
    "insights": "AI insights (with confidence)", "flags": "Risk flags to discuss", "guard": "Diagnostic Guard",
    "appointments": "Upcoming appointments",
}


def _fonts():
    try:
        pdfmetrics.registerFont(TTFont("DV", os.path.join(HERE, "assets", "fonts", "DejaVuSans.ttf")))
        pdfmetrics.registerFont(TTFont("DV-B", os.path.join(HERE, "assets", "fonts", "DejaVuSans-Bold.ttf")))
        return "DV", "DV-B"
    except Exception:
        return "Helvetica", "Helvetica-Bold"


def _table(rows, col_widths=None):
    t = Table(rows, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BLUE), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5), ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ("GRID", (0, 0), (-1, -1), 0.4, LINE), ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
    return t


def build_pdf(user_id: int, patient_name: str, include: dict[str, bool] | None = None) -> bytes:
    include = include or {k: True for k in SECTIONS}
    body_font, bold_font = _fonts()
    base = getSampleStyleSheet()
    body = ParagraphStyle("body", parent=base["Normal"], fontName=body_font, fontSize=9.2, leading=13)
    small = ParagraphStyle("small", parent=body, fontSize=7.8, textColor=SLATE, leading=11)
    h1 = ParagraphStyle("h1", parent=body, fontName=bold_font, fontSize=20, textColor=colors.HexColor("#0F172A"), spaceAfter=2)
    h2 = ParagraphStyle("h2", parent=body, fontName=bold_font, fontSize=12, textColor=BLUE, spaceBefore=12, spaceAfter=5)
    cell = ParagraphStyle("cell", parent=body, fontSize=8.5, leading=11)
    P = lambda text, st=body: Paragraph(escape(str(text)), st)
    C = lambda text: Paragraph(escape(str(text)), cell)

    story = [Paragraph("Consultation Preparation Summary", h1),
             P(f"Patient: {patient_name}   ·   Generated {date.today().strftime('%d %b %Y')}   ·   EchoCare", small),
             Spacer(1, 4),
             P("This document organises information the patient recorded themselves so it can be discussed with a "
               "licensed clinician. It is not a diagnosis and does not replace medical advice.", small)]

    def section(key, title, builder):
        if include.get(key):
            story.append(Paragraph(title, h2))
            builder()

    def s_survey():
        sv = db.get_survey(user_id)
        if not sv:
            return story.append(P("No survey on file."))
        rows = [["Field", "Answer"]]
        for grp in ("about_you", "main_concern", "care_context"):
            rows += [[C(k.replace("_", " ").title()), C(v)] for k, v in sv[grp].items() if v not in ("", None)]
        story.append(_table(rows, [50 * mm, 120 * mm]))

    def s_story():
        entries = db.get_story_entries(user_id)[:5]
        if not entries:
            return story.append(P("No story entries."))
        rows = [["Date", "What the patient reported", "Tagged areas"]]
        rows += [[C(e["created_at"][:10]), C(e["text"]), C(", ".join(e["extracted_symptoms"]))] for e in entries]
        story.append(_table(rows, [24 * mm, 110 * mm, 36 * mm]))

    def s_tracker():
        rows30 = db.get_tracker_range(user_id, (date.today() - timedelta(days=30)).isoformat())
        if not rows30:
            return story.append(P("No tracker data in the last 30 days."))
        avg = lambda k: (lambda v: f"{sum(v) / len(v):.1f}" if v else "n/a")([r[k] for r in rows30 if r.get(k) is not None])
        story.append(_table([["Sleep (h)", "Water (glasses)", "Stress /10", "Energy /10", "Pain /10", "Days logged"],
                             [avg("sleep_hours"), avg("water_glasses"), avg("stress_level"), avg("energy_level"), avg("pain_level"), len(rows30)]]))

    def s_vitals():
        v = db.get_vitals(user_id)
        if not v:
            return story.append(P("No vitals recorded."))
        rows = [["Date", "Weight", "BMI", "BP", "Fasting sugar", "Post-meal sugar"]]
        for r in v[-6:]:
            b, _ = hr.bmi(r.get("weight_kg"), r.get("height_cm"))
            bp = f"{r['systolic']}/{r['diastolic']}" if r.get("systolic") and r.get("diastolic") else "n/a"
            rows.append([r["entry_date"], f"{r['weight_kg']:g} kg" if r.get("weight_kg") else "n/a", b or "n/a", bp,
                         f"{r['fasting_sugar']:g}" if r.get("fasting_sugar") else "n/a",
                         f"{r['postmeal_sugar']:g}" if r.get("postmeal_sugar") else "n/a"])
        story.append(_table(rows))

    def s_labs():
        alerts = labs.latest_abnormal(labs.build_lab_series(db.get_reports(user_id)))
        if not alerts:
            return story.append(P("No out-of-range lab values on file."))
        rows = [["Test", "Latest", "Reference", "Direction", "Trend", "Date"]]
        for a in alerts:
            rows.append([C(a["label"]), C(f"{a['value']:g} {a.get('unit') or ''}"),
                         C(f"{a['low'] if a['low'] is not None else ''} - {a['high'] if a['high'] is not None else ''}"),
                         C(a["direction"]), C(a.get("trend") or "n/a"), C(a["date"])])
        story.append(_table(rows))

    def s_meds():
        meds = db.get_medicines(user_id)
        if not meds:
            return story.append(P("No active medicines."))
        rows = [["Medicine", "Dose", "Frequency", "Since"]] + [[C(m["name"]), C(m["dose"]), C(m["frequency"]), C(m["start_date"])] for m in meds]
        story.append(_table(rows))
        taken, expected = hr.adherence(user_id)
        if expected:
            story.append(P(f"7-day adherence: {taken}/{expected} doses logged ({round(100 * taken / expected)}%).", small))

    def s_insights():
        ins = db.get_insights(user_id)[:6]
        if not ins:
            return story.append(P("No insights generated."))
        rows = [["Theme", "Observation (discussion point)", "Confidence"]]
        rows += [[C(i["theme"].replace("_", " ")), C(i["text"]), C(f"{i['confidence_label']} ({round(i['confidence'] * 100)}%)")] for i in ins]
        story.append(_table(rows, [32 * mm, 108 * mm, 30 * mm]))

    def s_flags():
        flags = hr.compute_risk_flags(user_id)
        if not flags:
            return story.append(P("Nothing flagged."))
        rows = [["Priority", "Topic", "Detail"]] + [[C(f["level"]), C(f["title"]), C(f["detail"])] for f in flags]
        story.append(_table(rows, [22 * mm, 55 * mm, 93 * mm]))

    def s_guard():
        gaps = hr.symptom_gaps(user_id)
        ops = db.get_specialist_opinions(user_id)
        story.append(P("Recurring symptoms with no recorded resolution: " + (
            "; ".join(f"{g['symptom']} ({g['occurrences']}x)" for g in gaps) or "none")))
        if ops:
            rows = [["Specialist", "Department", "Opinion"]] + [[C(o["specialist_name"] or "n/a"), C(o["department"] or "n/a"), C(o["opinion_text"])] for o in ops]
            story.append(Spacer(1, 4))
            story.append(_table(rows, [35 * mm, 32 * mm, 103 * mm]))

    def s_appts():
        up = [a for a in db.get_appointments(user_id) if a["status"] == "scheduled" and a["appt_date"] >= date.today().isoformat()]
        if not up:
            return story.append(P("No upcoming appointments."))
        rows = [["Date", "Time", "Doctor", "Hospital"]] + [[C(a["appt_date"]), C(a["appt_time"]), C(a["doctor_name"]), C(a["hospital"])] for a in up]
        story.append(_table(rows))

    section("survey", "Survey summary", s_survey)
    section("story", "Recent story entries", s_story)
    section("tracker", "30-day tracker averages", s_tracker)
    section("vitals", "Vitals", s_vitals)
    section("labs", "Lab values outside reference range", s_labs)
    section("medicines", "Current medicines", s_meds)
    section("insights", "AI insights (discussion points)", s_insights)
    section("flags", "Risk flags worth discussing", s_flags)
    section("guard", "Diagnostic Guard", s_guard)
    section("appointments", "Upcoming appointments", s_appts)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm,
                            bottomMargin=16 * mm, title="EchoCare Consultation Summary", author="EchoCare")

    def footer(canvas, d):
        canvas.saveState()
        canvas.setFont(body_font, 7.5)
        canvas.setFillColor(SLATE)
        canvas.drawString(18 * mm, 9 * mm, "EchoCare · patient-reported information, not a diagnosis")
        canvas.drawRightString(A4[0] - 18 * mm, 9 * mm, f"Page {d.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buf.getvalue()
