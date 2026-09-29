import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import date, timedelta

import db, styles, ui, i18n, rag

user = ui.page_setup("Daily Tracker", "📈")
styles.hero(i18n.t("tracker_title"), "A minute a day builds real evidence over time.", eyebrow="Tracker")
st.markdown(styles.badge(f"🔥 {db.get_tracker_streak(user['id'])}-day streak", "demo"), unsafe_allow_html=True)

today = date.today().isoformat()
ex = db.get_tracker_entry(user["id"], today) or {}
tab_today, tab_week, tab_month = st.tabs(["Today", "This week", "This month"])

with tab_today:
    with st.form("tracker_form"):
        c1, c2 = st.columns(2)
        with c1:
            sleep = st.slider("Sleep (hours)", 0.0, 12.0, float(ex.get("sleep_hours") or 7.0), 0.5)
            water = st.slider("Water (glasses)", 0, 15, int(ex.get("water_glasses") or 6))
            stress = st.slider("Stress level (1-10)", 1, 10, int(ex.get("stress_level") or 4))
        with c2:
            energy = st.slider("Energy level (1-10)", 1, 10, int(ex.get("energy_level") or 6))
            pain = st.slider("Pain level (0-10)", 0, 10, int(ex.get("pain_level") or 0))
            notes = st.text_area("Notes", value=ex.get("notes") or "", height=100)
        submitted = st.form_submit_button(i18n.t("save_checkin"), type="primary")
    if submitted:
        db.upsert_tracker_entry(user["id"], today, sleep_hours=sleep, water_glasses=water, stress_level=stress,
                                energy_level=energy, pain_level=pain, notes=notes)
        rag.chunk_and_store(user["id"], "tracker",
                            f"On {today}: slept {sleep}h, drank {water} glasses of water, stress {stress}/10, "
                            f"energy {energy}/10, pain {pain}/10. {notes or ''}", {"date": today})
        st.success("Saved!")
        st.rerun()


def trend(days: int):
    rows = db.get_tracker_range(user["id"], (date.today() - timedelta(days=days)).isoformat())
    if not rows:
        return st.caption(f"No entries in the last {days} days yet.")
    df = pd.DataFrame(rows)
    fig = go.Figure()
    for col, name, color in [("sleep_hours", "Sleep (h)", "#2563EB"), ("energy_level", "Energy", "#16A34A"),
                             ("pain_level", "Pain", "#DC2626"), ("stress_level", "Stress", "#D97706")]:
        fig.add_trace(go.Scatter(x=df["entry_date"], y=df[col], name=name, mode="lines+markers", line=dict(color=color, width=2.5)))
    fig.update_layout(height=340, margin=dict(l=10, r=10, t=10, b=10), template="plotly_white",
                      legend=dict(orientation="h", y=1.12))
    st.plotly_chart(fig, use_container_width=True, key=f"trend_{days}")


with tab_week:
    trend(7)
with tab_month:
    trend(30)
