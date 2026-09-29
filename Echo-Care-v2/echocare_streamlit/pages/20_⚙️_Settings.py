import json
import streamlit as st

import auth, db, styles, ui, llm, rag

user = ui.page_setup("Settings", "⚙️")
styles.hero("Settings & Privacy", f"Managing data for: {user['name']}", eyebrow="Account")

st.markdown('<div class="ec-card">', unsafe_allow_html=True)
st.markdown("#### 🧠 AI services")
st.write(("🟢" if llm.gemini_configured() else "🔴") + " Gemini: text, Vision, voice transcription, embeddings")
st.write(("🟢" if llm.tavily_configured() else "🔴") + " Tavily: web grounding and interaction check")
if llm.embeddings_available() and st.button("Re-embed my evidence with Gemini"):
    n = rag.backfill_embeddings(user["id"], limit=500)
    st.success(f"Embedded {n} older evidence chunk(s).")
st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<div class="ec-card">', unsafe_allow_html=True)
st.markdown("#### Export data")
st.download_button("⬇️ Download all data for this profile (JSON)", json.dumps(db.export_all_data(user["id"]), indent=2, default=str),
                   "echocare_data_export.json", "application/json")
st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<div class="ec-card" style="border-color:#FECACA;">', unsafe_allow_html=True)
st.markdown("#### ⚠️ Danger zone")
account = auth.account_user()
is_member = user.get("is_member")
st.caption("Deletes this family profile and its data." if is_member else "Permanently deletes your account, all family profiles and every record.")
ok = st.checkbox("I understand this is permanent")
if st.button("Delete", disabled=not ok):
    if is_member:
        db.delete_member(account["id"], user["id"])
        auth.set_active_profile(None)
    else:
        db.delete_all_user_data(account["id"])
        auth.logout_user()
    st.rerun()
st.markdown('</div>', unsafe_allow_html=True)

st.markdown("#### Feedback")
with st.form("fb"):
    ctx = st.selectbox("About", ["Doctor recommendation", "An AI insight", "Echo chat", "Appointments", "General"])
    text = st.text_area("Tell us more")
    rating = st.slider("Rating", 1, 5, 4)
    if st.form_submit_button("Submit", type="primary"):
        db.insert_feedback(account["id"], ctx, text, rating)
        st.success("Thank you!")
