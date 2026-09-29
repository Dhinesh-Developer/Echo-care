import streamlit as st
from datetime import date, datetime

import db, styles, ui, i18n, llm, health_rules as hr

user = ui.page_setup("Medicines", "💊")
styles.hero(i18n.t("medicines_title"), "Schedule, reminders, adherence, and an interaction check.", eyebrow="Medicines")

FREQ = {"Once daily (morning)": ["Morning"], "Once daily (night)": ["Night"], "Twice daily": ["Morning", "Night"],
        "Three times daily": ["Morning", "Afternoon", "Night"]}
SLOT_DEADLINE_HOUR = {"Morning": 12, "Afternoon": 17, "Night": 22}
today = date.today().isoformat()
meds = db.get_medicines(user["id"])

tab_today, tab_add, tab_inter = st.tabs(["Today's schedule", "Add medicine", "Interaction check"])

with tab_today:
    if not meds:
        st.info("No medicines yet. Add one in the next tab, or import from a prescription photo on **Medical Reports**.")
    logs = {(l["medicine_id"], l["slot"]): l["taken"] for l in db.get_dose_logs(user["id"], today) if l["log_date"] == today}
    now_h = datetime.now().hour
    overdue = []
    for m in meds:
        if m.get("end_date") and m["end_date"] < today:
            continue
        st.markdown(f"**{m['name']}** {m['dose'] or ''} · _{m['frequency']}_" + (f"  \n<span style='color:var(--muted);font-size:.8rem;'>{m['notes']}</span>" if m.get("notes") else ""), unsafe_allow_html=True)
        cols = st.columns(len(m["slots"]) or 1)
        for col, slot in zip(cols, m["slots"]):
            with col:
                taken = st.checkbox(f"{slot}", value=bool(logs.get((m["id"], slot))), key=f"dose_{m['id']}_{slot}_{today}")
                if taken != bool(logs.get((m["id"], slot))):
                    db.log_dose(user["id"], m["id"], today, slot, taken)
                    st.rerun()
                if not taken and now_h >= SLOT_DEADLINE_HOUR[slot]:
                    overdue.append(f"{m['name']} ({slot})")
    if overdue:
        st.warning("⏰ **Reminder:** not yet logged today: " + ", ".join(overdue))
    taken_n, expected = hr.adherence(user["id"])
    if expected:
        pct = round(100 * taken_n / expected)
        st.progress(min(pct / 100, 1.0), text=f"7-day adherence: {taken_n}/{expected} doses ({pct}%)")
    if meds:
        st.divider()
        stop = st.selectbox("Stop a medicine", [None] + [m["id"] for m in meds], format_func=lambda i: "Select..." if i is None else next(m["name"] for m in meds if m["id"] == i))
        if stop and st.button("Mark as stopped"):
            db.set_medicine_active(user["id"], stop, False)
            st.rerun()

with tab_add:
    with st.form("med_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        name = c1.text_input("Medicine name", placeholder="Metformin")
        dose = c2.text_input("Dose", placeholder="500 mg")
        freq = st.selectbox("How often?", list(FREQ))
        c3, c4 = st.columns(2)
        start = c3.date_input("Start date", value=date.today())
        end = c4.date_input("End date (optional)", value=None)
        notes = st.text_input("Notes", placeholder="after food")
        if st.form_submit_button("Add medicine", type="primary") and name.strip():
            db.add_medicine(user["id"], name.strip(), dose.strip(), freq, FREQ[freq], start.isoformat(), end.isoformat() if end else None, notes)
            st.success("Added.")
            st.rerun()

with tab_inter:
    st.caption("Web-grounded check using Tavily. Informational only: always confirm with a pharmacist or doctor.")
    names = [m["name"] for m in meds]
    picked = st.multiselect("Choose medicines from your list", names, default=names[:2])
    extra = st.text_input("...or add another medicine to check (optional)")
    combo = picked + ([extra.strip()] if extra.strip() else [])
    if st.button("Check interactions", type="primary", disabled=len(combo) < 2):
        if not llm.tavily_configured():
            st.warning("Set `TAVILY_API_KEY` to enable the web-grounded interaction check.")
        else:
            with st.spinner("Searching trusted sources..."):
                res = llm.tavily_search("drug interaction between " + " and ".join(combo), max_results=4)
            if not res["ok"] or not res["results"]:
                st.warning("No sources found right now.")
            else:
                if llm.gemini_configured():
                    ctx = "\n".join(f"- {r['title']}: {(r['content'] or '')[:400]}" for r in res["results"])
                    summ = llm.gemini_generate(f"Medicines: {', '.join(combo)}\nSources:\n{ctx}\n\nSummarise, ONLY from these sources, whether an interaction is reported "
                                               "between these medicines. If sources don't say, say so. Do not advise stopping or changing any medicine; tell the user to confirm with a pharmacist or doctor.")
                    if summ["ok"]:
                        st.markdown(f'<div class="ec-card">{summ["text"]}</div>', unsafe_allow_html=True)
                for r in res["results"]:
                    st.markdown(f"**[{r['title']}]({r['url']})**  \n<span style='color:var(--muted);font-size:.85rem;'>{(r['content'] or '')[:220]}</span>", unsafe_allow_html=True)
                st.caption("This is not medical advice. Never stop or change a medicine because of this result.")
