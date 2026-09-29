import streamlit as st
import db, auth, styles, rag

st.set_page_config(page_title="Health Survey — EchoCare", page_icon="📋", layout="wide")
auth.require_login()
styles.inject()
user = auth.current_user()

styles.hero("Initial Health Survey", "A quick 3-step intake that feeds your evidence record.")

existing = db.get_survey(user["id"])
step = st.session_state.get("survey_step", (existing["step_complete"] if existing else 0))
step = min(step, 2)

tabs = st.tabs(["1. About You", "2. Main Concern", "3. Care Context"])

with st.form("survey_form"):
    with tabs[0]:
        age = st.text_input("Age", value=(existing or {}).get("about_you", {}).get("age", ""))
        sex = st.selectbox("Sex", ["", "Female", "Male", "Other", "Prefer not to say"],
                            index=0)
        occupation = st.text_input("Occupation", value=(existing or {}).get("about_you", {}).get("occupation", ""))
    with tabs[1]:
        description = st.text_area("Describe your main concern",
                                    value=(existing or {}).get("main_concern", {}).get("description", ""))
        duration = st.text_input("How long has this been going on?",
                                  value=(existing or {}).get("main_concern", {}).get("duration", ""))
        severity = st.slider("Severity (1-10)", 1, 10,
                              int((existing or {}).get("main_concern", {}).get("severity", 5) or 5))
    with tabs[2]:
        seen_doctor = st.selectbox("Have you seen a doctor about this?", ["", "Yes", "No", "Not yet, planning to"])
        medications = st.text_input("Current medications",
                                     value=(existing or {}).get("care_context", {}).get("medications", ""))
        goals = st.text_area("What would you like from your next visit?",
                              value=(existing or {}).get("care_context", {}).get("goals", ""))

    submitted = st.form_submit_button("Save survey", type="primary")

if submitted:
    about_you = {"age": age, "sex": sex, "occupation": occupation}
    main_concern = {"description": description, "duration": duration, "severity": severity}
    care_context = {"seen_doctor": seen_doctor, "medications": medications, "goals": goals}
    db.upsert_survey(user["id"], about_you, main_concern, care_context, 3)

    flat_text = " ".join(str(v) for section in (main_concern, care_context) for v in section.values() if v)
    if flat_text.strip():
        rag.chunk_and_store(user["id"], "survey", flat_text, {})
    st.success("Survey saved and added to your evidence record.")
    st.balloons()
