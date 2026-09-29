"""Month-grid HTML and .ics export for the Appointments page."""
import calendar
import html
from datetime import date, datetime, timedelta, timezone


def month_grid_html(year: int, month: int, appointments: list[dict]) -> str:
    by_day: dict[int, list[dict]] = {}
    for a in appointments:
        if a["status"] != "scheduled":
            continue
        d = date.fromisoformat(a["appt_date"])
        if d.year == year and d.month == month:
            by_day.setdefault(d.day, []).append(a)
    today = date.today()
    head = "".join(f"<th>{d}</th>" for d in ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"))
    rows = []
    for week in calendar.Calendar(firstweekday=0).monthdayscalendar(year, month):
        tds = []
        for day in week:
            if day == 0:
                tds.append("<td style='background:transparent;border:none;'></td>")
                continue
            appts = by_day.get(day, [])
            cls = ("today " if (year, month, day) == (today.year, today.month, today.day) else "") + ("has-appt" if appts else "")
            dots = "".join(f"<span class='dot'>{html.escape(a['appt_time'] or '')} {html.escape((a['doctor_name'] or '')[:14])}</span>" for a in appts[:2])
            more = f"<span class='dot'>+{len(appts) - 2} more</span>" if len(appts) > 2 else ""
            tds.append(f"<td class='{cls.strip()}'><b>{day}</b>{dots}{more}</td>")
        rows.append("<tr>" + "".join(tds) + "</tr>")
    return f"<table class='ec-cal'><tr>{head}</tr>{''.join(rows)}</table>"


def _esc(s: str) -> str:
    return (s or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def ics_event(appt: dict, minutes: int = 30) -> str:
    try:
        start = datetime.strptime(f"{appt['appt_date']} {appt.get('appt_time') or '09:00'}"[:16], "%Y-%m-%d %H:%M")
    except ValueError:
        start = datetime.strptime(appt["appt_date"], "%Y-%m-%d").replace(hour=9)
    end = start + timedelta(minutes=minutes)
    fmt = "%Y%m%dT%H%M%S"
    return "\r\n".join([
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//EchoCare//Appointments//EN", "BEGIN:VEVENT",
        f"UID:echocare-{appt['id']}@echocare", f"DTSTAMP:{datetime.now(timezone.utc).replace(tzinfo=None).strftime(fmt)}Z",
        f"DTSTART:{start.strftime(fmt)}", f"DTEND:{end.strftime(fmt)}",
        f"SUMMARY:{_esc('Appointment: ' + (appt.get('doctor_name') or 'Doctor'))}",
        f"LOCATION:{_esc(appt.get('hospital') or '')}",
        f"DESCRIPTION:{_esc((appt.get('specialty') or '') + '. ' + (appt.get('reason') or ''))}",
        "BEGIN:VALARM", "TRIGGER:-PT60M", "ACTION:DISPLAY", "DESCRIPTION:Appointment in 1 hour", "END:VALARM",
        "END:VEVENT", "END:VCALENDAR"])
