import streamlit as st
import plotly.graph_objects as go
from datetime import datetime, timedelta, timezone

import db, styles, ui, health_rules as hr
from specialties import SPECIALTIES

user = ui.page_setup("Health Timeline", "🧭")
styles.hero("Health Timeline & Risk Flags", "When each symptom area started and changed, plus patterns across your tracker, "
            "vitals, labs, medicines and story.", eyebrow="Patterns")

tab_tl, tab_flags = st.tabs(["🕒 Symptom timeline", "🚩 Risk flags"])

with tab_tl:
    chunks = [c for c in db.get_evidence_chunks(user["id"]) if any(t in SPECIALTIES for t in c["theme_tags"])]
    if not chunks:
        st.info("No symptom evidence yet. Add story entries, a survey, or tracker notes that mention symptoms.")
    else:
        SRC = {"narrative": ("#2563EB", "circle"), "survey": ("#7C3AED", "square"), "tracker": ("#16A34A", "diamond"),
               "report": ("#D97706", "triangle-up"), "vitals": ("#DB2777", "star"), "photo": ("#0891B2", "cross")}
        fig = go.Figure()
        for src, (color, symbol) in SRC.items():
            pts = [(datetime.fromisoformat(c["timestamp"]), t, c["text"][:90]) for c in chunks if c["source_type"] == src for t in c["theme_tags"] if t in SPECIALTIES]
            if pts:
                fig.add_trace(go.Scatter(x=[p[0] for p in pts], y=[p[1] for p in pts], mode="markers", name=src,
                                         text=[p[2] for p in pts], hovertemplate="%{y}<br>%{x|%d %b %H:%M}<br>%{text}<extra>" + src + "</extra>",
                                         marker=dict(size=13, color=color, symbol=symbol, line=dict(width=1, color="white"))))
        fig.update_layout(height=120 + 55 * len({t for c in chunks for t in c["theme_tags"] if t in SPECIALTIES}),
                          margin=dict(l=10, r=10, t=10, b=10), template="plotly_white", legend=dict(orientation="h", y=1.12),
                          yaxis=dict(categoryorder="category ascending"))
        st.plotly_chart(fig, use_container_width=True)

        rows, now = [], datetime.now(timezone.utc).replace(tzinfo=None)
        for theme in sorted({t for c in chunks for t in c["theme_tags"] if t in SPECIALTIES}):
            st_ = [datetime.fromisoformat(c["timestamp"]) for c in chunks if theme in c["theme_tags"]]
            recent = sum(1 for t in st_ if t >= now - timedelta(days=7))
            prior = sum(1 for t in st_ if now - timedelta(days=14) <= t < now - timedelta(days=7))
            trend = "more frequent ↗" if recent > prior else "less frequent ↘" if recent < prior else "steady →"
            rows.append({"Symptom area": theme, "First reported": min(st_).strftime("%d %b %Y"), "Latest": max(st_).strftime("%d %b %Y"),
                         "Mentions": len(st_), "Span (days)": (max(st_) - min(st_)).days, "Last 7d vs prior 7d": trend})
        st.dataframe(rows, use_container_width=True, hide_index=True)

with tab_flags:
    st.caption("Patterns that may be worth raising with a clinician. These are discussion points, **not** diagnoses.")
    flags = hr.compute_risk_flags(user["id"])
    if not flags:
        st.success("Nothing flagged right now. Keep logging tracker days, vitals and symptoms for a fuller picture.")
    for f in flags:
        disc = f["level"] == "discuss"
        st.markdown(f"""<div class="ec-card" style="border-left:5px solid {'#DC2626' if disc else '#D97706'};">
            {ui.status_badge('Worth discussing' if disc else 'Keep an eye on', 'alert' if disc else 'watch')}
            <span style="color:var(--muted);font-size:.75rem;margin-left:.5rem;">from: {', '.join(f['sources'])}</span>
            <div style="font-weight:700;margin-top:.4rem;">{f['title']}</div>
            <div style="color:var(--muted);font-size:.9rem;">{f['detail']}</div></div>""", unsafe_allow_html=True)
