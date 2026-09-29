import streamlit as st
import db, styles, ui, rag

user = ui.page_setup("Health Survey", "📋")
styles.hero("Initial Health Survey", "A quick 3-step intake that feeds your evidence record.", eyebrow="Onboarding")

ex = db.get_survey(user["id"]) or {"about_you": {}, "main_concern": {}, "care_context": {}}
tabs = st.tabs(["1 · About you", "2 · Main concern", "3 · Care context"])
with st.form("survey_form"):
    with tabs[0]:
        age = st.text_input("Age", value=ex["about_you"].get("age", ""))
        sexes = ["", "Female", "Male", "Other", "Prefer not to say"]
        sex = st.selectbox("Sex", sexes, index=sexes.index(ex["about_you"].get("sex", "")) if ex["about_you"].get("sex", "") in sexes else 0)
        occupation = st.text_input("Occupation", value=ex["about_you"].get("occupation", ""))
    with tabs[1]:
        description = st.text_area("Describe your main concern", value=ex["main_concern"].get("description", ""))
        duration = st.text_input("How long has this been going on?", value=ex["main_concern"].get("duration", ""))
        severity = st.slider("Severity (1-10)", 1, 10, int(ex["main_concern"].get("severity", 5) or 5))
    with tabs[2]:
        opts = ["", "Yes", "No", "Not yet, planning to"]
        seen = st.selectbox("Have you seen a doctor about this?", opts, index=opts.index(ex["care_context"].get("seen_doctor", "")) if ex["care_context"].get("seen_doctor", "") in opts else 0)
        medications = st.text_input("Current medications", value=ex["care_context"].get("medications", ""))
        goals = st.text_area("What would you like from your next visit?", value=ex["care_context"].get("goals", ""))
    submitted = st.form_submit_button("Save survey", type="primary")

if submitted:
    main = {"description": description, "duration": duration, "severity": severity}
    care = {"seen_doctor": seen, "medications": medications, "goals": goals}
    db.upsert_survey(user["id"], {"age": age, "sex": sex, "occupation": occupation}, main, care, 3)
    flat = " ".join(str(v) for sec in (main, care) for v in sec.values() if v)
    if flat.strip():
        rag.chunk_and_store(user["id"], "survey", flat, {})
    st.success("Survey saved and added to your evidence record.")
