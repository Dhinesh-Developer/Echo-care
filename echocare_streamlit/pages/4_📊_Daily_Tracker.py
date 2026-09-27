import streamlit as st
import pandas as pd
from datetime import date, timedelta

import db, auth, styles, rag

st.set_page_config(page_title="Daily Tracker — EchoCare", page_icon="📊", layout="wide")
auth.require_login()
styles.inject()
user = auth.current_user()

styles.hero("Daily Health Tracker", "A minute a day builds real evidence over time.")

streak = db.get_tracker_streak(user["id"])
st.markdown(styles.badge(f"🔥 {streak}-day streak", "demo"), unsafe_allow_html=True)

today_str = date.today().isoformat()
existing = db.get_tracker_entry(user["id"], today_str) or {}

tab_today, tab_week, tab_month = st.tabs(["Today", "This Week", "This Month"])

with tab_today:
    with st.form("tracker_form"):
        c1, c2 = st.columns(2)
        with c1:
            sleep_hours = st.slider("Sleep (hours)", 0.0, 12.0, float(existing.get("sleep_hours") or 7.0), 0.5)
            water = st.slider("Water (glasses)", 0, 15, int(existing.get("water_glasses") or 6))
            stress = st.slider("Stress level (1-10)", 1, 10, int(existing.get("stress_level") or 4))
        with c2:
            energy = st.slider("Energy level (1-10)", 1, 10, int(existing.get("energy_level") or 6))
            pain = st.slider("Pain level (0-10)", 0, 10, int(existing.get("pain_level") or 0))
            notes = st.text_area("Notes", value=existing.get("notes") or "", height=100)
        submitted = st.form_submit_button("Save today's check-in", type="primary")

    if submitted:
        db.upsert_tracker_entry(
            user["id"], today_str, sleep_hours=sleep_hours, water_glasses=water,
            stress_level=stress, energy_level=energy, pain_level=pain, notes=notes,
        )
        summary = (f"On {today_str}: slept {sleep_hours}h, drank {water} glasses of water, "
                   f"stress {stress}/10, energy {energy}/10, pain {pain}/10. {notes or ''}")
        rag.chunk_and_store(user["id"], "tracker", summary, {"date": today_str})
        st.success("Saved!")
        st.rerun()

with tab_week:
    rows = db.get_tracker_range(user["id"], (date.today() - timedelta(days=7)).isoformat())
    if rows:
        df = pd.DataFrame(rows)[["entry_date", "sleep_hours", "energy_level", "pain_level", "stress_level"]]
        df = df.set_index("entry_date")
        st.line_chart(df)
    else:
        st.caption("No entries in the last 7 days yet.")

with tab_month:
    rows = db.get_tracker_range(user["id"], (date.today() - timedelta(days=30)).isoformat())
    if rows:
        df = pd.DataFrame(rows)[["entry_date", "sleep_hours", "energy_level", "pain_level", "stress_level"]]
        df = df.set_index("entry_date")
        st.line_chart(df)
    else:
        st.caption("No entries in the last 30 days yet.")
