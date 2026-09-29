import streamlit as st
import plotly.graph_objects as go

import db, styles, ui, labs

user = ui.page_setup("Lab Trends", "🧪")
styles.hero("Lab Value Trends", "Follow each test across all your reports, against its reference range.", eyebrow="Labs")

series = labs.build_lab_series(db.get_reports(user["id"]))
if not series:
    st.info("No numeric lab values yet. Upload a report or add values manually on **Medical Reports**.")
    st.stop()

alerts = labs.latest_abnormal(series)
st.markdown("#### Out-of-range alerts (latest reading of each test)")
if alerts:
    cols = st.columns(min(3, len(alerts)))
    for i, a in enumerate(alerts):
        with cols[i % len(cols)]:
            arrow = {"rising": "↗ rising", "falling": "↘ falling", "steady": "→ steady"}.get(a["trend"], "single reading")
            st.markdown(f"""<div class="ec-card" style="border-color:#FECACA;">
                {ui.status_badge('Above range' if a['direction'] == 'high' else 'Below range', 'alert')}
                <div style="font-weight:700;margin-top:.4rem;">{a['label']}</div>
                <div style="font-size:1.4rem;font-weight:800;">{a['value']:g} <span style="font-size:.8rem;color:var(--muted);">{a.get('unit') or ''}</span></div>
                <div style="color:var(--muted);font-size:.8rem;">{arrow} · {a['date']}</div></div>""", unsafe_allow_html=True)
    st.caption("Values outside a reference range are common and not automatically a problem. Discuss them with your clinician.")
else:
    st.success("All of your latest values are within their reference ranges.")

st.divider()
test = st.selectbox("Choose a test", sorted(series, key=lambda k: (-len(series[k]), k)),
                    format_func=lambda k: f"{series[k][-1]['label']} ({len(series[k])} reading{'s' if len(series[k]) > 1 else ''})")
pts = series[test]
fig = go.Figure()
if pts[-1]["low"] is not None or pts[-1]["high"] is not None:
    lo = pts[-1]["low"] if pts[-1]["low"] is not None else min(p["value"] for p in pts) * 0.8
    hi = pts[-1]["high"] if pts[-1]["high"] is not None else max(p["value"] for p in pts) * 1.2
    fig.add_hrect(y0=lo, y1=hi, fillcolor="#16A34A", opacity=0.10, line_width=0, annotation_text="reference range")
fig.add_trace(go.Scatter(x=[p["date"] for p in pts], y=[p["value"] for p in pts], mode="lines+markers", name=pts[-1]["label"],
                         line=dict(color="#2563EB", width=3),
                         marker=dict(size=10, color=["#DC2626" if p["out_of_range"] else "#2563EB" for p in pts])))
fig.update_layout(height=380, margin=dict(l=10, r=10, t=10, b=10), template="plotly_white", yaxis_title=pts[-1].get("unit") or "value")
st.plotly_chart(fig, use_container_width=True)
if len(pts) < 2:
    st.caption("Only one reading so far. Add more reports to see a trend line.")
with st.expander("All readings"):
    st.dataframe([{"date": p["date"], "value": p["value"], "unit": p["unit"], "status": p["direction"] or "no range"} for p in pts],
                 use_container_width=True, hide_index=True)
