import streamlit as st

import db
import auth
import styles
import banner
import llm
from specialties import ALL_SPECIALTIES

st.set_page_config(
    page_title="EchoCare — AI Healthcare Companion",
    page_icon="🩺",
    layout="wide",
    initial_sidebar_state="expanded" if auth.current_user() else "collapsed",
)

db.init_db()
styles.inject()

user = auth.current_user()

# ---------------- Sidebar: identity + quick status ----------------
with st.sidebar:
    st.markdown("### 🩺 EchoCare")
    if user:
        st.success(f"Signed in as **{user['name']}**")
        if st.button("Log out", use_container_width=True):
            auth.logout_user()
            st.rerun()
        st.divider()
        st.caption("Use the pages above to navigate every module.")
    else:
        st.caption("Sign in on the home page to get started.")
    st.divider()
    st.caption("**Provider status**")
    st.caption(("🟢" if llm.gemini_configured() else "🔴") + " Gemini (generation)")
    st.caption(("🟢" if llm.tavily_configured() else "🔴") + " Tavily (web grounding)")

# ---------------- Hero ----------------
st.components.v1.html(banner.get_slideshow_html(height=300), height=310)

col1, col2 = st.columns([1.3, 1])
with col1:
    styles.hero(
        "EchoCare",
        "A longitudinal, evidence-grounded AI healthcare companion — track your "
        "story over time, get insights only when there's real evidence behind them, "
        "and find the right specialist, district by district.",
    )
    c1, c2, c3, c4 = st.columns(4)
    styles.stat_card(c1, "10", "Specialties covered")
    styles.stat_card(c2, "117", "Doctors in directory")
    styles.stat_card(c3, "10", "Districts mapped")
    styles.stat_card(c4, "24/7", "Emergency safety guard")

with col2:
    st.markdown('<div class="tuf-card">', unsafe_allow_html=True)
    if user:
        st.markdown(f"#### Welcome back, {user['name'].split()[0]} 👋")
        st.write("Jump to a module using the sidebar, or start here:")
        if st.button("Go to Dashboard →", use_container_width=True, type="primary"):
            st.switch_page("pages/1_📊_Dashboard.py")
    else:
        tab_login, tab_signup = st.tabs(["Log in", "Sign up"])
        with tab_login:
            with st.form("login_form"):
                email = st.text_input("Email")
                password = st.text_input("Password", type="password")
                submitted = st.form_submit_button("Log in", use_container_width=True, type="primary")
                if submitted:
                    ok, msg = auth.login_user(email, password)
                    if ok:
                        st.rerun()
                    else:
                        st.error(msg)
        with tab_signup:
            with st.form("signup_form"):
                name = st.text_input("Full name")
                email_s = st.text_input("Email", key="signup_email")
                password_s = st.text_input("Password (min 8 chars)", type="password", key="signup_pw")
                submitted_s = st.form_submit_button("Create account", use_container_width=True, type="primary")
                if submitted_s:
                    ok, msg = auth.register_user(name, email_s, password_s)
                    if ok:
                        st.rerun()
                    else:
                        st.error(msg)
    st.markdown('</div>', unsafe_allow_html=True)

st.divider()

# ---------------- Feature grid ----------------
st.markdown("### What's inside")
features = [
    ("📖", "My Story", "Free-text symptom narration, auto-tagged against 10 specialties."),
    ("📋", "Health Survey", "Structured 3-step intake that feeds your evidence record."),
    ("📊", "Daily Tracker", "Sleep, stress, energy, pain — with streaks and trend charts."),
    ("📄", "Medical Reports", "Upload a PDF/scan; OCR + field parsing extracts lab values."),
    ("✨", "AI Insights", "LE-RAG only surfaces a theme once there's real corroborating evidence."),
    ("💬", "Echo Companion", "A tool-using agent: your evidence + Tavily grounding + Gemini."),
    ("🛡️", "Diagnostic Guard", "Flags symptoms that persist unresolved and conflicting opinions."),
    ("🏥", "Find Doctors", "District-wise map across all 10 specialties, ranked for you."),
]
cols = st.columns(4)
for i, (icon, name, desc) in enumerate(features):
    with cols[i % 4]:
        st.markdown(f"""
            <div class="tuf-card" style="min-height:150px;">
                <div style="font-size:1.6rem;">{icon}</div>
                <div style="font-weight:700;margin-top:.3rem;">{name}</div>
                <div style="color:var(--muted);font-size:.82rem;margin-top:.2rem;">{desc}</div>
            </div>
        """, unsafe_allow_html=True)

st.divider()
st.markdown("### Specialties covered")
st.markdown(" ".join(styles.pill(s) for s in ALL_SPECIALTIES), unsafe_allow_html=True)

st.markdown(
    '<p class="tuf-disclaimer">EchoCare organizes your own reported health information for '
    'discussion with a licensed clinician. It never provides a diagnosis. Doctor directory data '
    'shown throughout the app is demo/seed data unless otherwise noted.</p>',
    unsafe_allow_html=True,
)
