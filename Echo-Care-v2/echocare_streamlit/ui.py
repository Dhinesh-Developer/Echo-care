"""Shared page scaffolding: page config, theme, login gate, sidebar (profile switcher, language,
provider status), and reusable components (explainable insight card, emergency card)."""
import html
import streamlit as st

import auth
import db
import i18n
import llm
import styles

STATUS_TO_BADGE = {"ok": "high", "watch": "moderate", "alert": "low"}


def status_badge(label: str, status: str) -> str:
    return styles.badge(label, STATUS_TO_BADGE.get(status, "demo"))


def page_setup(title: str, icon: str, need_login: bool = True, sidebar_state: str = "expanded"):
    st.set_page_config(page_title=f"{title} · EchoCare", page_icon=icon, layout="wide",
                       initial_sidebar_state=sidebar_state)
    db.init_db()
    styles.inject()
    if need_login:
        auth.require_login()
    render_sidebar()
    return auth.current_user()


NAV = [
    ("Track", [("pages/2_📖_My_Story.py", "My Story", "📖"), ("pages/3_📋_Health_Survey.py", "Health Survey", "📋"),
               ("pages/4_📈_Daily_Tracker.py", "Daily Tracker", "📈"), ("pages/5_💓_Vitals.py", "Vitals", "💓"),
               ("pages/8_💊_Medicines.py", "Medicines", "💊")]),
    ("Understand", [("pages/6_📄_Medical_Reports.py", "Reports & Photos", "📄"), ("pages/7_🧪_Lab_Trends.py", "Lab Trends", "🧪"),
                    ("pages/9_🧭_Health_Timeline.py", "Timeline & Risk Flags", "🧭"), ("pages/10_✨_AI_Insights.py", "AI Insights", "✨"),
                    ("pages/11_💬_Echo_Companion.py", "Echo Companion", "💬"), ("pages/12_🛡️_Diagnostic_Guard.py", "Diagnostic Guard", "🛡️")]),
    ("Care", [("pages/13_🏥_Find_Doctors.py", "Find Doctors", "🏥"), ("pages/14_📅_Appointments.py", "Appointments", "📅"),
              ("pages/16_🚑_Emergency_Card.py", "Emergency Card", "🚑"), ("pages/17_📑_Consultation_Report.py", "PDF Report", "📑"),
              ("pages/15_👪_Family_Profiles.py", "Family Profiles", "👪")]),
    ("Account", [("pages/18_🧘_Wellness.py", "Wellness", "🧘"), ("pages/20_⚙️_Settings.py", "Settings", "⚙️")]),
]


def _link(path: str, label: str, icon: str):
    """st.page_link only resolves the full page registry when Streamlit serves Home.py as the actual
    multipage entrypoint. Fall back to a plain (non-clickable) label rather than crash the page —
    this only ever triggers in isolated test/preview contexts, never in a real `streamlit run Home.py`."""
    try:
        st.page_link(path, label=label, icon=icon)
    except Exception:
        st.caption(f"{icon} {label}")


def _nav():
    _link("Home.py", "Home", "🏠")
    if not auth.account_user():
        return
    _link("pages/1_📊_Dashboard.py", "Dashboard", "📊")
    for group, pages in NAV:
        st.caption(group.upper())
        for path, label, icon in pages:
            _link(path, label, icon)
    if auth.is_admin():
        st.caption("ADMIN")
        _link("pages/19_🔐_Admin.py", "Admin dashboard", "🔐")


def render_sidebar():
    with st.sidebar:
        st.markdown("### 🩺 EchoCare")
        _nav()
        st.divider()
        account = auth.account_user()
        if account:
            members = db.get_members(account["id"])
            if members:
                ids = [account["id"]] + [m["id"] for m in members]
                names = {account["id"]: f"{account['name']} (me)"}
                names.update({m["id"]: f"{m['name']} ({m['relation']})" for m in members})
                current = auth.current_user()["id"]
                choice = st.selectbox("Viewing profile", ids, index=ids.index(current), format_func=names.get)
                if choice != current:
                    auth.set_active_profile(None if choice == account["id"] else choice)
                    st.rerun()
            else:
                st.caption(f"Signed in as **{account['name']}**")
            if st.button("Log out", use_container_width=True):
                auth.logout_user()
                st.rerun()
        st.divider()
        labels = list(i18n.LANGS)
        codes = list(i18n.LANGS.values())
        picked = st.selectbox("🌐 Language / மொழி / भाषा", labels, index=codes.index(i18n.get_lang()))
        if i18n.LANGS[picked] != i18n.get_lang():
            st.session_state["lang"] = i18n.LANGS[picked]
            st.rerun()
        st.divider()
        st.caption("**AI services**")
        st.caption(("🟢" if llm.gemini_configured() else "🔴") + " Gemini (text, vision, voice, embeddings)")
        st.caption(("🟢" if llm.tavily_configured() else "🔴") + " Tavily (web grounding)")


def insight_card(ins: dict, user_id: int):
    """Insight with an 'explain this' expander: retrieval method, confidence math, the exact evidence."""
    kind = ins["confidence_label"]
    st.markdown(f"""
        <div class="ec-card" style="margin-bottom:.3rem;">
            <div style="display:flex;justify-content:space-between;align-items:center;">
                <span style="color:var(--muted);font-size:.75rem;text-transform:uppercase;letter-spacing:.05em;">
                    {html.escape(ins['theme'].replace('_', ' '))}</span>
                {styles.badge(f"{kind} · {round(ins['confidence'] * 100)}%", kind)}
            </div>
            <p style="margin:.6rem 0;">{html.escape(ins['text'])}</p>
            <p style="color:var(--muted);font-size:.78rem;margin:0;">{html.escape(ins['evidence_summary'])}</p>
            <p class="ec-disclaimer">Not a diagnosis: a discussion point for your clinician, based only on the
            evidence shown. Generated by: {html.escape(str(ins['generated_by']))}</p>
        </div>""", unsafe_allow_html=True)
    with st.expander("🔍 Why am I seeing this? Evidence & confidence"):
        bd = ins.get("confidence_breakdown") or {}
        if bd:
            st.caption(f"Retrieval method: **{bd.get('retrieval', 'n/a')}**")
            weights = {"similarity": ("Evidence relevance", 0.40), "source_diversity": ("Source diversity", 0.25),
                       "occurrence_rate": ("How often it recurs", 0.20), "temporal_consistency": ("Persistence over time", 0.15)}
            for key, (label, w) in weights.items():
                if key in bd:
                    st.progress(min(max(float(bd[key]), 0.0), 1.0), text=f"{label}: {round(bd[key] * 100)}%  (weight {int(w * 100)}%)")
        chunks = db.get_evidence_chunks_by_ids(user_id, ins.get("evidence_chunk_ids", []))
        st.markdown("**Evidence used:**")
        for c in chunks:
            st.markdown(f"- `{c['source_type']}` · {c['timestamp'][:10]}: {html.escape(c['text'])}")
        if not chunks:
            st.caption("The underlying evidence entries are no longer available.")


def render_emergency_card(data: dict, name: str, public: bool = False):
    e = lambda v: html.escape(str(v)) if v else "<span style='color:var(--muted)'>Not provided</span>"
    contacts = "".join(
        f"<div style='margin:.2rem 0;'><b>{html.escape(c.get('name', ''))}</b> "
        f"({html.escape(c.get('relation', ''))}): <a href='tel:{html.escape(c.get('phone', ''))}'>{html.escape(c.get('phone', ''))}</a></div>"
        for c in data.get("contacts", []) if c.get("name") or c.get("phone")) or "<span style='color:var(--muted)'>Not provided</span>"
    st.markdown(f"""
        <div class="ec-card" style="border:2px solid #DC2626;padding:0;overflow:hidden;">
            <div style="background:#DC2626;color:white;padding:.8rem 1.2rem;font-weight:800;letter-spacing:.04em;">
                🚑 EMERGENCY MEDICAL CARD</div>
            <div style="padding:1.1rem 1.3rem;">
                <div style="font-size:1.5rem;font-weight:800;">{html.escape(name)}</div>
                <table style="width:100%;margin-top:.7rem;border-collapse:collapse;font-size:.92rem;">
                    <tr><td style="width:170px;color:var(--muted);padding:.35rem 0;">Blood group</td><td><b style="color:#DC2626;font-size:1.15rem;">{e(data.get('blood_group'))}</b></td></tr>
                    <tr><td style="color:var(--muted);padding:.35rem 0;">Allergies</td><td>{e(data.get('allergies'))}</td></tr>
                    <tr><td style="color:var(--muted);padding:.35rem 0;">Chronic conditions</td><td>{e(data.get('conditions'))}</td></tr>
                    <tr><td style="color:var(--muted);padding:.35rem 0;">Current medicines</td><td>{e(data.get('medications'))}</td></tr>
                    <tr><td style="color:var(--muted);padding:.35rem 0;">Regular doctor</td><td>{e(data.get('doctor_name'))} {html.escape(data.get('doctor_phone', '') or '')}</td></tr>
                    <tr><td style="color:var(--muted);padding:.35rem 0;">Organ donor</td><td>{e(data.get('organ_donor'))}</td></tr>
                    <tr><td style="color:var(--muted);padding:.35rem 0;">Notes</td><td>{e(data.get('notes'))}</td></tr>
                </table>
                <div style="margin-top:.8rem;font-weight:700;">Emergency contacts</div>{contacts}
                <div class="ec-disclaimer">Self-reported information. In an emergency call <b>112</b> (India).
                {"This page is public: anyone with the link can see it." if public else ""}</div>
            </div>
        </div>""", unsafe_allow_html=True)
