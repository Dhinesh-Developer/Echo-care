import streamlit as st
import json

import db, auth, styles

st.set_page_config(page_title="Settings — EchoCare", page_icon="⚙️", layout="wide")
auth.require_login()
styles.inject()
user = auth.current_user()

styles.hero("Settings & Privacy", "Manage your data.")

st.markdown('<div class="tuf-card">', unsafe_allow_html=True)
st.markdown("#### Export your data")
st.caption("Everything you've entered — story, tracker, reports, insights, chat, opinions.")
data = db.export_all_data(user["id"])
st.download_button(
    "⬇️ Download my data (JSON)", json.dumps(data, indent=2, default=str),
    file_name="echocare_data_export.json", mime="application/json",
)
st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<div class="tuf-card" style="border-color:var(--danger);">', unsafe_allow_html=True)
st.markdown("#### ⚠️ Danger zone")
st.caption("Permanently deletes your account and every record tied to it. Cannot be undone.")
confirm = st.checkbox("I understand this is permanent")
if st.button("Delete my account and all data", disabled=not confirm, type="primary"):
    db.delete_all_user_data(user["id"])
    auth.logout_user()
    st.success("Account deleted.")
    st.rerun()
st.markdown('</div>', unsafe_allow_html=True)

st.divider()
st.markdown("#### Give feedback")
with st.form("feedback_form"):
    context = st.selectbox("What's this about?", ["Department recommendation", "Doctor visit", "An AI insight", "General"])
    outcome = st.text_area("Tell us more")
    rating = st.slider("Rating", 1, 5, 3)
    if st.form_submit_button("Submit"):
        db.insert_feedback(user["id"], context, outcome, rating)
        st.success("Thank you — this helps improve future recommendations.")
