import html
import streamlit as st

import db, styles, ui, llm, compare, health_rules as hr

user = ui.page_setup("Diagnostic Guard", "🛡️")
styles.hero("Diagnostic Guard", "Symptoms that keep coming back unresolved, and opinions that may not agree, "
            "so nothing falls through the cracks.", eyebrow="Advocacy")

gaps = hr.symptom_gaps(user["id"])
opinions = db.get_specialist_opinions(user["id"])

tab_gaps, tab_ops, tab_cmp, tab_brief = st.tabs(["Unresolved patterns", "Specialist opinions", "Compare side by side", "Advocacy brief"])

with tab_gaps:
    if not gaps:
        st.caption("None detected yet.")
    for g in gaps:
        st.markdown(f"""<div class="ec-card"><b>{html.escape(g['symptom'].replace('_', ' '))}</b>: reported {g['occurrences']} times,
            {g['first'].date()} to {g['last'].date()}, with no resolution recorded.</div>""", unsafe_allow_html=True)

with tab_ops:
    with st.form("opinion_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        who, dept = c1.text_input("Specialist name"), c2.text_input("Department")
        text = st.text_area("What did they say?")
        if st.form_submit_button("Add opinion", type="primary") and text.strip():
            db.insert_specialist_opinion(user["id"], who, dept, text)
            st.rerun()
    for o in opinions:
        st.markdown(f'<div class="ec-card"><b>{html.escape(o["specialist_name"] or "Unnamed")}</b> ({html.escape(o["department"] or "N/A")}): {html.escape(o["opinion_text"])}</div>', unsafe_allow_html=True)

with tab_cmp:
    if len(opinions) < 2:
        st.info("Add at least two specialist opinions to compare them.")
    else:
        label = lambda i: f"{opinions[i]['specialist_name'] or 'Unnamed'} ({opinions[i]['department'] or 'N/A'})"
        c1, c2 = st.columns(2)
        a = c1.selectbox("Opinion A", range(len(opinions)), format_func=label, index=0)
        b = c2.selectbox("Opinion B", range(len(opinions)), format_func=label, index=1)
        if a == b:
            st.warning("Pick two different opinions.")
        else:
            ha, hb = compare.diff_html(opinions[a]["opinion_text"], opinions[b]["opinion_text"])
            col_a, col_b = st.columns(2)
            col_a.markdown(f'<div class="ec-card"><b>{html.escape(label(a))}</b><p style="margin-top:.5rem;">{ha}</p></div>', unsafe_allow_html=True)
            col_b.markdown(f'<div class="ec-card"><b>{html.escape(label(b))}</b><p style="margin-top:.5rem;">{hb}</p></div>', unsafe_allow_html=True)
            sig = compare.conflict_signals(opinions[a]["opinion_text"], opinions[b]["opinion_text"])
            if sig["possible_conflict"]:
                st.error("⚠️ **Possible conflict:** both discuss " + ", ".join(sig["shared_terms"][:4]) + ", but one contains negating/reassuring language the other lacks. Worth asking both clinicians to reconcile this.")
            else:
                st.success("No obvious conflict signals from wording alone.")
            st.caption(f"Wording similarity {sig['similarity']} · shared terms: {', '.join(sig['shared_terms']) or 'none'} · highlighted text differs between the two.")
            if st.button("Ask Gemini to judge this pair") :
                res = llm.gemini_generate(f"Opinion A: {opinions[a]['opinion_text']}\nOpinion B: {opinions[b]['opinion_text']}\n\nDo these agree, contradict, or is it unclear? "
                                          "Answer with one word (agree/contradict/unclear) then one short sentence why. Do not add medical advice.")
                st.info(res["text"] if res["ok"] else f"Gemini unavailable: {res.get('reason')}")

with tab_brief:
    lines = ["# Advocacy Brief\n", "## Unresolved symptom patterns"]
    lines += [f"- **{g['symptom'].replace('_', ' ').title()}**: {g['occurrences']} occurrences ({g['first'].date()} to {g['last'].date()})" for g in gaps] or ["- none"]
    lines.append("\n## Specialist opinions on file")
    lines += [f"- {o['specialist_name'] or 'Unknown'} ({o['department'] or 'N/A'}): {o['opinion_text']}" for o in opinions] or ["- none"]
    lines.append("\n_Organises your own reported history for discussion with a licensed clinician. Not a diagnosis._")
    brief = "\n".join(lines)
    st.download_button("⬇️ Download brief (Markdown)", brief, "advocacy_brief.md", "text/markdown", type="primary")
    st.markdown(brief)
