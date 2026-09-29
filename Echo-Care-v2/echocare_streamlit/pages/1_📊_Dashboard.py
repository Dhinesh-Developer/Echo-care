import streamlit as st
from datetime import date, timedelta

import db, styles, ui, i18n, health_rules as hr

user = ui.page_setup("Dashboard", "📊")
styles.hero(i18n.t("dashboard_title"), f"{i18n.t('welcome_back')}, {user['name'].split()[0]}.", eyebrow="Overview")

TIPS = ["Aim for 7–9 hours of sleep", "Drink water regularly through the day", "A 30-minute walk counts as exercise",
        "Log your symptoms the same day: memory fades fast", "Bring your PDF summary to your next appointment",
        "Take medicines at the same time each day", "Check BP seated, after 5 minutes of rest"]
styles.ticker(TIPS)

recent = db.get_tracker_range(user["id"], (date.today() - timedelta(days=7)).isoformat())


def health_score(entries):
    scores = []
    for e in entries:
        parts = []
        if e.get("sleep_hours") is not None: parts.append(min(e["sleep_hours"] / 8, 1) * 100)
        if e.get("stress_level") is not None: parts.append((10 - e["stress_level"]) / 10 * 100)
        if e.get("energy_level") is not None: parts.append(e["energy_level"] / 10 * 100)
        if e.get("pain_level") is not None: parts.append((10 - e["pain_level"]) / 10 * 100)
        if parts: scores.append(sum(parts) / len(parts))
    return round(sum(scores) / len(scores)) if scores else "n/a"


taken, expected = hr.adherence(user["id"])
c1, c2, c3, c4, c5 = st.columns(5)
styles.stat_card(c1, health_score(recent), "Health score (7d)")
styles.stat_card(c2, f"{db.get_tracker_streak(user['id'])} ", "Tracking streak")
styles.stat_card(c3, len(db.get_story_entries(user["id"])), "Story entries")
styles.stat_card(c4, len(db.get_insights(user["id"])), "Insights")
styles.stat_card(c5, f"{round(100 * taken / expected)}%" if expected else "n/a", "Medicine adherence (7d)")

st.write("")
left, right = st.columns([1.15, 1])
with left:
    st.markdown("#### Recent insights")
    insights = db.get_insights(user["id"])[:3]
    if not insights:
        st.info("No insights yet. Add a story entry and a few tracker days, then open **AI Insights**.")
    for ins in insights:
        ui.insight_card(ins, user["id"])
with right:
    st.markdown("#### Worth discussing with your clinician")
    flags = hr.compute_risk_flags(user["id"])[:4]
    if not flags:
        st.success("Nothing flagged right now. Keep logging to build a clearer picture.")
    for f in flags:
        st.markdown(f"""<div class="ec-card" style="padding:.9rem 1.1rem;">
            {ui.status_badge('Discuss' if f['level'] == 'discuss' else 'Watch', 'alert' if f['level'] == 'discuss' else 'watch')}
            <div style="font-weight:600;margin-top:.4rem;">{f['title']}</div>
            <div style="color:var(--muted);font-size:.84rem;">{f['detail']}</div></div>""", unsafe_allow_html=True)
    appts = [a for a in db.get_appointments(user["id"]) if a["status"] == "scheduled" and a["appt_date"] >= date.today().isoformat()][:2]
    if appts:
        st.markdown("#### Upcoming")
        for a in appts:
            st.markdown(f"📅 **{a['appt_date']} {a['appt_time']}**: {a['doctor_name']} ({a['specialty']})")

st.divider()
q = st.columns(5)
targets = [("📖 Add story", "pages/2_📖_My_Story.py"), ("📈 Log today", "pages/4_📈_Daily_Tracker.py"),
           ("💬 Ask Echo", "pages/11_💬_Echo_Companion.py"), ("🏥 Find doctor", "pages/13_🏥_Find_Doctors.py"),
           ("📑 PDF report", "pages/17_📑_Consultation_Report.py")]
for col, (label, target) in zip(q, targets):
    with col:
        if st.button(label, use_container_width=True):
            st.switch_page(target)
