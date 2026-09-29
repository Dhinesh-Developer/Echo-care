import html
import streamlit as st

import db, styles, ui, i18n, llm, rag
from safety import check_emergency, EMERGENCY_MESSAGE, EMERGENCY_RESOURCES

user = ui.page_setup("My Story", "📖")
styles.hero(i18n.t("story_title"), i18n.t("story_sub") + " Type it, or just speak.", eyebrow="Symptoms")

# ---- Voice input (Gemini transcription: English / Tamil / Hindi) ----
if hasattr(st, "audio_input"):
    audio = st.audio_input(i18n.t("record_voice"))
    if audio is not None and st.button("Transcribe recording", type="primary"):
        with st.spinner("Transcribing with Gemini..."):
            res = llm.gemini_transcribe(audio.getvalue(), "audio/wav")
        if res["ok"] and res["text"]:
            st.session_state["story_text"] = res["text"].strip()
            st.rerun()
        else:
            st.warning(f"Transcription unavailable: {res.get('reason')}")

with st.form("story_form", clear_on_submit=True):
    text = st.text_area("What's going on?", key="story_text", height=140,
                        placeholder="e.g. I've had a dull headache and trouble sleeping for the past week, worse in the evenings...")
    submitted = st.form_submit_button(i18n.t("save_entry"), type="primary")

if submitted and text.strip():
    if check_emergency(text):
        st.error(EMERGENCY_MESSAGE)
        for name, contact in EMERGENCY_RESOURCES:
            st.write(f"**{name}:** {contact}")
    else:
        db.insert_story_entry(user["id"], text, rag.tag_themes(text), rag.extract_timeline(text))
        rag.chunk_and_store(user["id"], "narrative", text, {})
        st.success("Entry saved and added to your evidence record.")
        st.rerun()

st.divider()
st.markdown("#### Past entries")
entries = db.get_story_entries(user["id"])
if not entries:
    st.caption("No entries yet.")
for e in entries:
    tags = " ".join(styles.pill(s.replace("_", " ")) for s in e["extracted_symptoms"])
    tl = f'<div style="color:var(--accent);font-size:.8rem;margin-top:4px;">⏱ {html.escape(e["timeline"])}</div>' if e.get("timeline") else ""
    st.markdown(f"""<div class="ec-card"><p style="margin:0;">{html.escape(e['text'])}</p>
        <div style="margin-top:8px;">{tags}</div>{tl}
        <p style="color:var(--muted);font-size:.75rem;margin:6px 0 0 0;">{e['created_at'][:16].replace('T', ' ')}</p></div>""",
                unsafe_allow_html=True)
