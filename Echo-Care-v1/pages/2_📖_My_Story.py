import streamlit as st

import db, auth, styles, rag
from safety import check_emergency, EMERGENCY_MESSAGE, EMERGENCY_RESOURCES

st.set_page_config(page_title="My Story — EchoCare", page_icon="📖", layout="wide")
auth.require_login()
styles.inject()
user = auth.current_user()

styles.hero("My Story", "Describe what you're experiencing in your own words. "
                        "This feeds your evidence record — nothing here produces a diagnosis.")

with st.form("story_form", clear_on_submit=True):
    text = st.text_area(
        "What's going on?", height=140,
        placeholder="e.g. I've had a dull headache and trouble sleeping for the past week, "
                    "especially in the evenings...",
    )
    submitted = st.form_submit_button("Save entry", type="primary")

if submitted and text.strip():
    if check_emergency(text):
        st.markdown('<div class="tuf-card" style="border-color:var(--danger);">', unsafe_allow_html=True)
        st.error(EMERGENCY_MESSAGE)
        for name, contact in EMERGENCY_RESOURCES:
            st.write(f"**{name}:** {contact}")
        st.markdown('</div>', unsafe_allow_html=True)
    else:
        symptoms = rag.tag_themes(text)
        timeline = rag.extract_timeline(text)
        db.insert_story_entry(user["id"], text, symptoms, timeline)
        rag.chunk_and_store(user["id"], "narrative", text, {})
        st.success("Entry saved and added to your evidence record.")
        st.rerun()

st.divider()
st.markdown("### Past entries")
entries = db.get_story_entries(user["id"])
if not entries:
    st.caption("No entries yet.")
for e in entries:
    tags_html = " ".join(styles.pill(s.replace("_", " ")) for s in e["extracted_symptoms"])
    timeline_html = f'<div style="color:var(--accent-2);font-size:.8rem;margin-top:4px;">⏱ {e["timeline"]}</div>' if e.get("timeline") else ""
    st.markdown(f"""
        <div class="tuf-card">
            <p style="margin:0;">{e['text']}</p>
            <div style="margin-top:8px;">{tags_html}</div>
            {timeline_html}
            <p style="color:var(--muted);font-size:.75rem;margin-top:6px;">{e['created_at'][:16].replace('T',' ')}</p>
        </div>
    """, unsafe_allow_html=True)
