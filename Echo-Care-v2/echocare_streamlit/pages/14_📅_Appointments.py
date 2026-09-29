import html
import streamlit as st
from datetime import date, time, timedelta

import db, styles, ui, i18n, calendar_utils as cu, doctors_data as dd

user = ui.page_setup("Appointments", "📅")
styles.hero(i18n.t("appointments_title"), "Book, see them on a calendar, get reminders, and add them to your phone calendar.", eyebrow="Care coordination")

today = date.today()
appts = db.get_appointments(user["id"])
upcoming = [a for a in appts if a["status"] == "scheduled" and a["appt_date"] >= today.isoformat()]

# ---- reminders ----
for a in upcoming:
    days = (date.fromisoformat(a["appt_date"]) - today).days
    if days <= 1:
        st.warning(f"⏰ **{'Today' if days == 0 else 'Tomorrow'}** {a['appt_time']}: {a['doctor_name']} ({a['specialty']}) at {a['hospital'] or 'the clinic'}")

tab_book, tab_cal, tab_list = st.tabs(["➕ Book", "🗓️ Calendar", "📋 All appointments"])

with tab_book:
    pre = st.session_state.get("book_doctor")
    directory = dd.get_directory()
    options = ["Enter manually"] + [f"{d['name']} · {d['specialty']} · {d['hospital']}, {d['district']}" for d in directory]
    idx = 0
    if pre:
        key = f"{pre['name']} · {pre['specialty']} · {pre['hospital']}, {pre['district']}"
        idx = options.index(key) if key in options else 0
        st.info(f"Selected from Find Doctors: **{pre['name']}**")
    choice = st.selectbox("Doctor", options, index=idx)
    with st.form("appt_form", clear_on_submit=True):
        if choice == "Enter manually":
            c1, c2, c3 = st.columns(3)
            dname, dspec, dhosp = c1.text_input("Doctor name"), c2.text_input("Specialty"), c3.text_input("Hospital / clinic")
        else:
            d = directory[options.index(choice) - 1]
            dname, dspec, dhosp = d["name"], d["specialty"], f"{d['hospital']}, {d['district']}"
            st.caption(f"{dname} · {dspec} · {dhosp} · ₹{d['consultation_fee_inr']}")
        c1, c2 = st.columns(2)
        adate = c1.date_input("Date", value=today + timedelta(days=1), min_value=today)
        atime = c2.time_input("Time", value=time(10, 0), step=900)
        reason = st.text_input("Reason for visit")
        notes = st.text_area("Notes / questions to ask", height=80)
        if st.form_submit_button("Book appointment", type="primary"):
            clash = [a for a in upcoming if a["appt_date"] == adate.isoformat() and a["appt_time"] == atime.strftime("%H:%M")]
            if not dname.strip():
                st.error("Enter a doctor name.")
            elif clash:
                st.error(f"You already have an appointment at that time with {clash[0]['doctor_name']}.")
            else:
                db.add_appointment(user["id"], dname.strip(), dspec, dhosp, adate.isoformat(), atime.strftime("%H:%M"), reason, notes)
                st.session_state.pop("book_doctor", None)
                st.success("Booked. It's saved in your calendar and reminders.")
                st.rerun()
    st.caption("This records your booking in EchoCare. Please also confirm with the clinic, as EchoCare does not contact hospitals.")

with tab_cal:
    y, m = st.session_state.get("cal_y", today.year), st.session_state.get("cal_m", today.month)
    c1, c2, c3 = st.columns([1, 3, 1])
    if c1.button("◀ Prev"):
        y, m = (y - 1, 12) if m == 1 else (y, m - 1)
        st.session_state.update(cal_y=y, cal_m=m); st.rerun()
    if c3.button("Next ▶"):
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
        st.session_state.update(cal_y=y, cal_m=m); st.rerun()
    c2.markdown(f"<h4 style='text-align:center;margin:0;'>{date(y, m, 1).strftime('%B %Y')}</h4>", unsafe_allow_html=True)
    st.markdown(cu.month_grid_html(y, m, appts), unsafe_allow_html=True)

with tab_list:
    if not appts:
        st.caption("No appointments yet.")
    for a in sorted(appts, key=lambda x: (x["appt_date"], x["appt_time"]), reverse=True):
        badge = {"scheduled": "demo", "completed": "high", "cancelled": "low"}[a["status"]]
        st.markdown(f"""<div class="ec-card" style="margin-bottom:.3rem;"><div style="display:flex;justify-content:space-between;">
            <div><b>{a['appt_date']} · {a['appt_time']}</b> · {html.escape(a['doctor_name'] or '')} ({html.escape(a['specialty'] or '')})<br>
            <span style="color:var(--muted);font-size:.85rem;">{html.escape(a['hospital'] or '')} · {html.escape(a['reason'] or '')}</span></div>
            {styles.badge(a['status'], badge)}</div></div>""", unsafe_allow_html=True)
        if a["status"] == "scheduled":
            b1, b2, b3, _ = st.columns([1, 1, 1.4, 3])
            if b1.button("✅ Done", key=f"done_{a['id']}"):
                db.update_appointment_status(user["id"], a["id"], "completed"); st.rerun()
            if b2.button("✖ Cancel", key=f"cancel_{a['id']}"):
                db.update_appointment_status(user["id"], a["id"], "cancelled"); st.rerun()
            b3.download_button("📲 Add to calendar", cu.ics_event(a), f"appointment_{a['id']}.ics", "text/calendar", key=f"ics_{a['id']}")
