import streamlit as st
import time

import db, auth, styles, llm

st.set_page_config(page_title="Wellness — EchoCare", page_icon="🧘", layout="wide")
auth.require_login()
styles.inject()
user = auth.current_user()

styles.hero("Wellness & Self-Care Tools", "Quick tools for the moment, plus grounded tips via Tavily.")

tab1, tab2, tab3 = st.tabs(["🫁 Box Breathing", "📝 Journaling", "🌐 Grounded Tips"])

with tab1:
    st.markdown("**Box breathing**: inhale 4s → hold 4s → exhale 4s → hold 4s. Repeat for 2 minutes.")
    if st.button("Start 60-second guided round"):
        phases = [("Inhale...", 4), ("Hold...", 4), ("Exhale...", 4), ("Hold...", 4)] * 3
        ph = st.empty()
        bar = st.progress(0)
        total = sum(p[1] for p in phases)
        elapsed = 0
        for label, secs in phases:
            for s in range(secs, 0, -1):
                ph.markdown(f"### {label} {s}")
                elapsed += 1
                bar.progress(min(elapsed / total, 1.0))
                time.sleep(1)
        ph.markdown("### Done — nice work 🌿")

with tab2:
    prompt_choices = [
        "What's one thing that felt heavy today, and one thing that felt light?",
        "Describe your energy in three words. What shaped it?",
        "What would you tell a friend feeling exactly like you do right now?",
    ]
    st.markdown(f"**Prompt:** {prompt_choices[hash(user['email']) % len(prompt_choices)]}")
    entry = st.text_area("Write freely — this stays private to you.", height=150)
    if st.button("Save journal note") and entry.strip():
        db.insert_feedback(user["id"], "journaling", entry, None)
        st.success("Saved.")

with tab3:
    topic = st.text_input("Topic", value="stress management")
    if st.button("Get grounded tips", type="primary"):
        if not llm.tavily_configured():
            st.warning("`TAVILY_API_KEY` isn't configured — tips are unavailable right now.")
        else:
            with st.spinner("Searching..."):
                result = llm.tavily_search(f"{topic} self-care tips evidence based")
            if not result["ok"]:
                st.error(f"Tavily search failed: {result.get('reason') or 'unknown provider error'}")
            elif result["results"]:
                for r in result["results"]:
                    st.markdown(f"**[{r['title']}]({r['url']})**")
                    st.caption((r["content"] or "")[:280])
            else:
                st.info("Tavily returned no sources for this topic. Try a different search phrase.")
