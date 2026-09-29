import time
import streamlit as st
import db, styles, ui, llm

user = ui.page_setup("Wellness", "🧘")
styles.hero("Wellness & Self-Care", "Quick tools for the moment, plus web-grounded tips.", eyebrow="Wellness")
tab1, tab2, tab3, tab4 = st.tabs(["🫁 Box breathing", "🌿 5-4-3-2-1 grounding", "📝 Journal", "🌐 Grounded tips"])

with tab1:
    st.markdown("Inhale 4s → hold 4s → exhale 4s → hold 4s.")
    if st.button("Start a guided round", type="primary"):
        ph, bar = st.empty(), st.progress(0)
        phases = [("Inhale", 4), ("Hold", 4), ("Exhale", 4), ("Hold", 4)] * 3
        total, done = sum(p[1] for p in phases), 0
        for label, secs in phases:
            for s in range(secs, 0, -1):
                ph.markdown(f"### {label} · {s}")
                done += 1
                bar.progress(done / total)
                time.sleep(1)
        ph.markdown("### Done. Nice work 🌿")
with tab2:
    for n, sense in [(5, "things you can **see**"), (4, "things you can **touch**"), (3, "things you can **hear**"),
                     (2, "things you can **smell**"), (1, "thing you can **taste**")]:
        st.checkbox(f"Name {n} {sense}", key=f"g{n}")
with tab3:
    st.markdown("**Prompt:** What felt heavy today, and what felt light?")
    entry = st.text_area("Write freely. It stays private to this profile.", height=140)
    if st.button("Save journal note") and entry.strip():
        db.insert_feedback(user["id"], "journaling", entry, None)
        st.success("Saved.")
with tab4:
    topic = st.text_input("Topic", value="stress management")
    if st.button("Get grounded tips", type="primary"):
        if not llm.tavily_configured():
            st.warning("`TAVILY_API_KEY` isn't configured.")
        else:
            res = llm.tavily_search(f"{topic} self-care tips evidence based")
            for r in res["results"]:
                st.markdown(f"**[{r['title']}]({r['url']})**  \n<span style='color:var(--muted);font-size:.85rem;'>{(r['content'] or '')[:260]}</span>", unsafe_allow_html=True)
            if not res["results"]:
                st.caption("No results right now.")
