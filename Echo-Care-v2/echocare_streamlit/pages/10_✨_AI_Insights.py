import streamlit as st
import db, styles, ui, rag, llm

user = ui.page_setup("AI Insights", "✨")
styles.hero("AI Health Insights", "A theme is surfaced only when there's real corroborating evidence. "
            "Open any insight to see exactly why.", eyebrow="Explainable AI")

if llm.embeddings_available():
    st.success("🧠 Semantic retrieval is on: Gemini embeddings match meaning, not just keywords.")
else:
    st.info("Keyword retrieval (TF-IDF) is active. Add `GOOGLE_API_KEY` to switch to semantic retrieval and to generate insight text.")

if st.button("✨ Generate new insights", type="primary"):
    with st.spinner("Embedding evidence, checking sufficiency gates, generating..."):
        new = rag.generate_insights(user["id"], llm.gemini_generate)
        for ins in new:
            db.insert_insight(user["id"], ins)
    st.success(f"Generated {len(new)} insight(s)." if new else "No theme has enough corroborating evidence yet (needs 2+ mentions across 2+ source types).")
    st.rerun()

st.divider()
insights = db.get_insights(user["id"])
if not insights:
    st.info("No insights yet. Add a story entry, complete your survey, or log a few tracker days.")
cols = st.columns(2)
for i, ins in enumerate(insights):
    with cols[i % 2]:
        ui.insight_card(ins, user["id"])
