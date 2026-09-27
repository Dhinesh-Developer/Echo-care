import streamlit as st
from datetime import datetime

import db, auth, styles, llm

st.set_page_config(page_title="Diagnostic Guard — EchoCare", page_icon="🛡️", layout="wide")
auth.require_login()
styles.inject()
user = auth.current_user()

styles.hero("Diagnostic Guard", "Flags symptoms that keep coming up unresolved, and possible "
                                "contradictions between specialist opinions — so nothing quietly falls through the cracks.")

UNRESOLVED_WINDOW_THRESHOLD = 2


def detect_symptom_gaps():
    chunks = db.get_evidence_chunks(user["id"])
    by_theme = {}
    for c in chunks:
        for tag in c["theme_tags"]:
            if tag == "general_wellbeing":
                continue
            by_theme.setdefault(tag, []).append(datetime.fromisoformat(c["timestamp"]))
    gaps = []
    for theme, timestamps in by_theme.items():
        weeks = {t.isocalendar()[1] for t in timestamps}
        if len(weeks) >= UNRESOLVED_WINDOW_THRESHOLD or len(timestamps) >= 3:
            gaps.append({"symptom": theme, "occurrences": len(timestamps),
                         "first": min(timestamps), "last": max(timestamps)})
    return gaps


def detect_contradictions(opinions):
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    contradictions = []
    if len(opinions) < 2:
        return contradictions
    texts = [o["opinion_text"] for o in opinions]
    vec = TfidfVectorizer(stop_words="english")
    try:
        matrix = vec.fit_transform(texts)
    except ValueError:
        return contradictions
    sims = cosine_similarity(matrix)
    for i in range(len(opinions)):
        for j in range(i + 1, len(opinions)):
            sim = sims[i][j]
            if 0.15 < sim < 0.6:
                prompt = (f"Opinion A: {opinions[i]['opinion_text']}\nOpinion B: {opinions[j]['opinion_text']}\n\n"
                          "Do these agree, contradict, or is it unclear? Answer with exactly one word: "
                          "agree, contradict, or unclear.")
                result = llm.gemini_generate(prompt)
                stance = "unclear"
                if result["ok"] and result["text"]:
                    low = result["text"].strip().lower()
                    stance = "contradict" if "contradict" in low else ("agree" if "agree" in low else "unclear")
                if stance == "contradict":
                    contradictions.append({"a": opinions[i]["opinion_text"], "b": opinions[j]["opinion_text"],
                                            "similarity": round(float(sim), 3)})
    return contradictions


st.markdown("### Unresolved symptom patterns")
gaps = detect_symptom_gaps()
if gaps:
    for g in gaps:
        st.markdown(f"""
            <div class="tuf-card">
                <strong>{g['symptom'].replace('_',' ')}</strong> — reported {g['occurrences']} times,
                from {g['first'].date()} to {g['last'].date()}, with no resolution recorded.
            </div>
        """, unsafe_allow_html=True)
else:
    st.caption("None detected yet.")

st.divider()
st.markdown("### Specialist opinions on file")
with st.form("opinion_form", clear_on_submit=True):
    c1, c2 = st.columns(2)
    with c1:
        specialist_name = st.text_input("Specialist name")
    with c2:
        department = st.text_input("Department")
    opinion_text = st.text_area("What did they say?")
    if st.form_submit_button("Add opinion", type="primary") and opinion_text.strip():
        db.insert_specialist_opinion(user["id"], specialist_name, department, opinion_text)
        st.success("Opinion recorded.")
        st.rerun()

opinions = db.get_specialist_opinions(user["id"])
for o in opinions:
    st.markdown(f"""
        <div class="tuf-card"><strong>{o['specialist_name'] or 'Unnamed'}</strong>
        ({o['department'] or 'N/A'}): {o['opinion_text']}</div>
    """, unsafe_allow_html=True)

st.divider()
st.markdown("### Possible contradictions")
if len(opinions) >= 2:
    if st.button("🔍 Check for contradictions"):
        with st.spinner("Comparing opinions..."):
            contradictions = detect_contradictions(opinions)
        if contradictions:
            for c in contradictions:
                st.markdown(f"""
                    <div class="tuf-card" style="border-color:var(--warn);">
                        "{c['a']}" <br/> vs <br/> "{c['b']}"
                        <div style="color:var(--muted);font-size:.78rem;">similarity: {c['similarity']}</div>
                    </div>
                """, unsafe_allow_html=True)
        else:
            st.caption("No contradictions detected among current opinions.")
else:
    st.caption("Add at least 2 specialist opinions to check for contradictions.")

st.divider()
if st.button("📋 Export advocacy brief"):
    lines = ["# Advocacy Brief\n"]
    lines.append("## Unresolved symptom patterns")
    for g in gaps:
        lines.append(f"- **{g['symptom'].replace('_',' ').title()}** — {g['occurrences']} occurrences "
                     f"({g['first'].date()} to {g['last'].date()})")
    lines.append("\n## Specialist opinions on file")
    for o in opinions:
        lines.append(f"- {o['specialist_name'] or 'Unknown'} ({o['department'] or 'N/A'}): {o['opinion_text']}")
    lines.append("\n_This brief organizes your own reported history for discussion with a licensed clinician. It is not a diagnosis._")
    brief = "\n".join(lines)
    st.download_button("Download brief (Markdown)", brief, file_name="advocacy_brief.md", mime="text/markdown")
    st.markdown(brief)
