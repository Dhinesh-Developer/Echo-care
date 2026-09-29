import streamlit as st
from datetime import date, timedelta

import db, auth, styles

st.set_page_config(page_title="Dashboard — EchoCare", page_icon="📊", layout="wide")
auth.require_login()
styles.inject()
user = auth.current_user()

styles.hero("Your Health Dashboard", f"Welcome back, {user['name'].split()[0]}.")

streak = db.get_tracker_streak(user["id"])
recent = db.get_tracker_range(user["id"], (date.today() - timedelta(days=7)).isoformat())
insights = db.get_insights(user["id"])

def health_score(entries):
    if not entries:
        return 0
    scores = []
    for e in entries:
        parts = []
        if e.get("sleep_hours") is not None:
            parts.append(min(e["sleep_hours"] / 8, 1.0) * 100)
        if e.get("stress_level") is not None:
            parts.append((10 - e["stress_level"]) / 10 * 100)
        if e.get("energy_level") is not None:
            parts.append(e["energy_level"] / 10 * 100)
        if e.get("pain_level") is not None:
            parts.append((10 - e["pain_level"]) / 10 * 100)
        if parts:
            scores.append(sum(parts) / len(parts))
    return round(sum(scores) / len(scores)) if scores else 0

c1, c2, c3, c4 = st.columns(4)
styles.stat_card(c1, health_score(recent), "Health score (7d)")
styles.stat_card(c2, f"{streak} 🔥", "Tracking streak")
styles.stat_card(c3, len(db.get_story_entries(user["id"])), "Story entries")
styles.stat_card(c4, len(insights), "Insights generated")

st.divider()
st.markdown("### Recent Insights")
if insights:
    for i in insights[:4]:
        kind = i["confidence_label"]
        st.markdown(f"""
            <div class="tuf-card">
                <div style="display:flex;justify-content:space-between;">
                    <span style="color:var(--muted);font-size:.78rem;text-transform:uppercase;">{i['theme'].replace('_',' ')}</span>
                    {styles.badge(f"{kind} confidence ({round(i['confidence']*100)}%)", kind)}
                </div>
                <p style="margin:.5rem 0 0 0;">{i['text']}</p>
                <p style="color:var(--muted);font-size:.78rem;">{i['evidence_summary']}</p>
            </div>
        """, unsafe_allow_html=True)
else:
    st.info("No insights yet — add a story entry or a few tracker days, then visit **AI Insights** to generate one.")

st.divider()
st.markdown("### Quick actions")
qc1, qc2, qc3, qc4 = st.columns(4)
with qc1:
    if st.button("📖 Add story entry", use_container_width=True):
        st.switch_page("pages/2_📖_My_Story.py")
with qc2:
    if st.button("📊 Log today", use_container_width=True):
        st.switch_page("pages/4_📊_Daily_Tracker.py")
with qc3:
    if st.button("💬 Talk to Echo", use_container_width=True):
        st.switch_page("pages/7_💬_Echo_Companion.py")
with qc4:
    if st.button("🏥 Find a doctor", use_container_width=True):
        st.switch_page("pages/9_🏥_Find_Doctors.py")
