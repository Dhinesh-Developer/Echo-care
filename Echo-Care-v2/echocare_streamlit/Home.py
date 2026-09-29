import streamlit as st

import auth, banner, db, i18n, llm, styles, ui
from specialties import ALL_SPECIALTIES

db.init_db()

# ---- Public emergency card (no login): /?card=<token> ----
token = st.query_params.get("card")
if token:
    st.set_page_config(page_title="Emergency Card · EchoCare", page_icon="🚑", layout="centered", initial_sidebar_state="collapsed")
    styles.inject()
    st.markdown("<style>[data-testid='stSidebar'],[data-testid='collapsedControl']{display:none;}</style>", unsafe_allow_html=True)
    card = db.get_emergency_card_by_token(token)
    if card:
        ui.render_emergency_card(card["data"], card["name"], public=True)
    else:
        st.error("This emergency card link is invalid or has been turned off by its owner.")
    st.stop()

user = ui.page_setup("Home", "🩺", need_login=False, sidebar_state="expanded")
account = auth.account_user()

st.markdown(banner.get_slideshow_html(), unsafe_allow_html=True)
styles.ticker(["Semantic evidence retrieval with Gemini embeddings", "Read lab reports and prescriptions from a photo",
               "Speak your symptoms in English, Tamil or Hindi", "Find doctors district by district and navigate there",
               "Medicine reminders and interaction checks", "One-click PDF summary for your doctor",
               "Emergency card with a shareable QR code", "Family profiles under one login"])

left, right = st.columns([1.35, 1])
with left:
    styles.hero("EchoCare", "One platform for your whole health story: track it, understand it with explainable AI, "
                "and take it to the right doctor, in your language.", eyebrow="AI healthcare companion")
    import doctors_data as dd
    n_docs = len(dd.get_directory())
    c1, c2, c3, c4 = st.columns(4)
    styles.stat_card(c1, "20", "Modules")
    styles.stat_card(c2, len(ALL_SPECIALTIES), "Specialties")
    styles.stat_card(c3, n_docs, "Doctors listed")
    styles.stat_card(c4, "3", "Languages")

with right:
    if account:
        st.markdown(f'<div class="ec-card"><h4 style="margin:0 0 .3rem 0;">{i18n.t("welcome_back")}, {account["name"].split()[0]} 👋</h4>'
                    '<p style="color:var(--muted);margin:0 0 .8rem 0;">Pick a module from the sidebar, or jump in:</p></div>', unsafe_allow_html=True)
        if st.button("Open my dashboard →", type="primary", use_container_width=True):
            st.switch_page("pages/1_📊_Dashboard.py")
    else:
        tab_login, tab_signup = st.tabs(["Log in", "Sign up"])
        with tab_login:
            with st.form("login_form"):
                email = st.text_input("Email")
                pw = st.text_input("Password", type="password")
                if st.form_submit_button("Log in", type="primary", use_container_width=True):
                    ok, msg = auth.login_user(email, pw)
                    if ok:
                        st.rerun()
                    else:
                        st.error(msg)
        with tab_signup:
            with st.form("signup_form"):
                name = st.text_input("Full name")
                email_s = st.text_input("Email", key="signup_email")
                pw_s = st.text_input("Password (min 8 characters)", type="password", key="signup_pw")
                if st.form_submit_button("Create account", type="primary", use_container_width=True):
                    ok, msg = auth.register_user(name, email_s, pw_s)
                    if ok:
                        st.rerun()
                    else:
                        st.error(msg)

st.divider()
st.markdown("### Everything in one platform")
FEATURES = [
    ("📖", "My Story", "Type or speak symptoms; auto-tagged to 10 specialties."), ("📋", "Health Survey", "3-step intake feeding your evidence record."),
    ("📈", "Daily Tracker", "Sleep, stress, energy, pain with streaks and charts."), ("💓", "Vitals", "BMI, blood pressure and sugar against target ranges."),
    ("📄", "Reports & Photos", "Gemini Vision reads labs, prescriptions and photos."), ("🧪", "Lab Trends", "Each test across reports with out-of-range alerts."),
    ("💊", "Medicines", "Reminders, adherence and web-grounded interaction check."), ("🧭", "Timeline & Risk Flags", "Symptom timeline and cross-source patterns."),
    ("✨", "AI Insights", "Semantic RAG with a full 'why am I seeing this?' view."), ("💬", "Echo Companion", "Agent that asks follow-ups, then answers from your evidence."),
    ("🛡️", "Diagnostic Guard", "Unresolved symptoms and side-by-side opinion comparison."), ("🏥", "Find Doctors", "District map, ranking, navigation and live search."),
    ("📅", "Appointments", "Booking, calendar view, reminders, .ics export."), ("👪", "Family Profiles", "Track parents or children under one login."),
    ("🚑", "Emergency Card", "Public QR-linked card for responders."), ("📑", "PDF Report", "One-click summary to hand to your doctor."),
]
cols = st.columns(4)
for i, (icon, name, desc) in enumerate(FEATURES):
    with cols[i % 4]:
        st.markdown(f'<div class="ec-card" style="min-height:140px;"><div style="font-size:1.5rem;">{icon}</div>'
                    f'<div style="font-weight:700;margin-top:.3rem;">{name}</div>'
                    f'<div style="color:var(--muted);font-size:.82rem;margin-top:.2rem;">{desc}</div></div>', unsafe_allow_html=True)

st.markdown("### Specialties covered")
st.markdown(" ".join(styles.pill(s) for s in ALL_SPECIALTIES), unsafe_allow_html=True)
st.markdown('<p class="ec-disclaimer">EchoCare organises your own reported information for discussion with a licensed clinician. '
            'It never provides a diagnosis. Doctor data is demo data unless an admin imports a real directory. In an emergency call 112.</p>',
            unsafe_allow_html=True)