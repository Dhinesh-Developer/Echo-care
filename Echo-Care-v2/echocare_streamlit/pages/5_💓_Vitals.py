import streamlit as st
import plotly.graph_objects as go
from datetime import date

import db, styles, ui, i18n, rag, health_rules as hr

user = ui.page_setup("Vitals", "💓")
styles.hero(i18n.t("vitals_title"), "Log measurements and see them against the usual target ranges.", eyebrow="Vitals")

vitals = db.get_vitals(user["id"])
last_height = next((v["height_cm"] for v in reversed(vitals) if v.get("height_cm")), 0.0)

with st.form("vitals_form"):
    d = st.date_input("Date", value=date.today(), max_value=date.today())
    c1, c2, c3 = st.columns(3)
    with c1:
        weight = st.number_input("Weight (kg)", 0.0, 300.0, 0.0, 0.1)
        height = st.number_input("Height (cm)", 0.0, 250.0, float(last_height or 0.0), 0.5)
    with c2:
        sys_ = st.number_input("Systolic BP (mmHg)", 0, 300, 0)
        dia = st.number_input("Diastolic BP (mmHg)", 0, 200, 0)
    with c3:
        fasting = st.number_input("Fasting sugar (mg/dL)", 0.0, 600.0, 0.0, 1.0)
        post = st.number_input("Post-meal sugar, 2 h (mg/dL)", 0.0, 800.0, 0.0, 1.0)
    st.caption("Leave a field at 0 if you didn't measure it.")
    submitted = st.form_submit_button("Save readings", type="primary")

if submitted:
    vals = dict(weight_kg=weight or None, height_cm=height or None, systolic=sys_ or None, diastolic=dia or None,
                fasting_sugar=fasting or None, postmeal_sugar=post or None)
    if not any(vals.values()):
        st.warning("Enter at least one reading.")
    else:
        db.upsert_vitals(user["id"], d.isoformat(), **vals)
        parts = []
        b, bcat = hr.bmi(weight, height)
        if b: parts.append(f"BMI {b} ({bcat[0]})")
        if sys_ and dia: parts.append(f"blood pressure {sys_}/{dia} mmHg ({hr.bp_category(sys_, dia)[0]})")
        if fasting: parts.append(f"fasting sugar {fasting:g} mg/dL ({hr.fasting_sugar_category(fasting)[0]})")
        if post: parts.append(f"post-meal sugar {post:g} mg/dL ({hr.postmeal_sugar_category(post)[0]})")
        if parts:
            rag.chunk_and_store(user["id"], "vitals", f"On {d.isoformat()}: " + ", ".join(parts) + ".", {"date": d.isoformat()})
        st.success("Readings saved.")
        if sys_ and dia and hr.bp_category(sys_, dia)[1] == "alert" and (sys_ > 180 or dia > 120):
            st.error("This blood pressure is in a range that needs urgent medical attention. Call 112 or go to the nearest emergency department.")
        st.rerun()

vitals = db.get_vitals(user["id"])
if vitals:
    last = lambda k: next((v[k] for v in reversed(vitals) if v.get(k)), None)
    cards = st.columns(4)
    b, bcat = hr.bmi(last("weight_kg"), last("height_cm"))
    sysv, diav = last("systolic"), last("diastolic")
    bpc = hr.bp_category(sysv, diav)
    fs, ps = last("fasting_sugar"), last("postmeal_sugar")
    items = [("BMI", f"{b}" if b else "n/a", bcat), ("Blood pressure", f"{sysv}/{diav}" if bpc else "n/a", bpc),
             ("Fasting sugar", f"{fs:g}" if fs else "n/a", hr.fasting_sugar_category(fs)),
             ("Post-meal sugar", f"{ps:g}" if ps else "n/a", hr.postmeal_sugar_category(ps))]
    for col, (label, val, cat) in zip(cards, items):
        with col:
            badge = ui.status_badge(cat[0], cat[1]) if cat else ""
            st.markdown(f'<div class="ec-stat"><div class="label">{label}</div><div class="num">{val}</div>{badge}</div>', unsafe_allow_html=True)

    st.write("")
    t1, t2, t3 = st.tabs(["Blood pressure", "Blood sugar", "Weight & BMI"])
    layout = dict(height=340, margin=dict(l=10, r=10, t=10, b=10), template="plotly_white", legend=dict(orientation="h", y=1.12))
    with t1:
        bp = [v for v in vitals if v.get("systolic")]
        if bp:
            fig = go.Figure()
            fig.add_hrect(y0=90, y1=120, fillcolor="#16A34A", opacity=0.08, line_width=0, annotation_text="target systolic")
            fig.add_hrect(y0=60, y1=80, fillcolor="#2563EB", opacity=0.08, line_width=0, annotation_text="target diastolic")
            fig.add_trace(go.Scatter(x=[v["entry_date"] for v in bp], y=[v["systolic"] for v in bp], name="Systolic", mode="lines+markers", line=dict(color="#DC2626")))
            fig.add_trace(go.Scatter(x=[v["entry_date"] for v in bp], y=[v["diastolic"] for v in bp], name="Diastolic", mode="lines+markers", line=dict(color="#2563EB")))
            fig.update_layout(**layout)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.caption("No blood pressure readings yet.")
    with t2:
        sg = [v for v in vitals if v.get("fasting_sugar") or v.get("postmeal_sugar")]
        if sg:
            fig = go.Figure()
            fig.add_hrect(y0=70, y1=99, fillcolor="#16A34A", opacity=0.08, line_width=0, annotation_text="fasting target")
            fig.add_trace(go.Scatter(x=[v["entry_date"] for v in sg], y=[v.get("fasting_sugar") for v in sg], name="Fasting", mode="lines+markers", line=dict(color="#2563EB"), connectgaps=True))
            fig.add_trace(go.Scatter(x=[v["entry_date"] for v in sg], y=[v.get("postmeal_sugar") for v in sg], name="Post-meal", mode="lines+markers", line=dict(color="#D97706"), connectgaps=True))
            fig.update_layout(**layout)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.caption("No sugar readings yet.")
    with t3:
        wt = [v for v in vitals if v.get("weight_kg")]
        if wt:
            fig = go.Figure(go.Scatter(x=[v["entry_date"] for v in wt], y=[v["weight_kg"] for v in wt], name="Weight (kg)", mode="lines+markers", line=dict(color="#2563EB")))
            fig.update_layout(**layout)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.caption("No weight readings yet.")

with st.expander("📏 Target ranges used on this page"):
    for name, target, note in hr.TARGETS:
        st.markdown(f"**{name}**: {target}  \n<span style='color:var(--muted);font-size:.85rem;'>{note}</span>", unsafe_allow_html=True)
    st.caption("General adult reference ranges for orientation only. Your clinician may set different targets for you.")
