"""
Shared CSS — clean, modern light SaaS design system: near-white background,
blue primary accent, near-black text, rounded cards with subtle borders and
shadows, pill buttons, spacious dashboard-style layout.
"""
import streamlit as st

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

:root {
    --bg: #F8FAFC;
    --surface: #FFFFFF;
    --surface-2: #F1F5F9;
    --border: #E2E8F0;
    --accent: #2563EB;
    --accent-2: #1D4ED8;
    --accent-soft: #EFF6FF;
    --accent-grad: linear-gradient(135deg, #2563EB 0%, #3B82F6 100%);
    --text: #0F172A;
    --muted: #64748B;
    --success: #16A34A;
    --warn: #D97706;
    --danger: #DC2626;
    --shadow: 0 1px 2px rgba(15,23,42,.04), 0 6px 16px rgba(15,23,42,.05);
}

html, body, [class*="css"], .stApp {
    font-family: 'Inter', -apple-system, 'Segoe UI', Roboto, sans-serif !important;
}
.stApp { background: var(--bg); color: var(--text); }
.block-container { padding-top: 2rem; max-width: 1200px; }

/* ---------- Cards ---------- */
.ec-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 1.25rem 1.4rem;
    margin-bottom: 1rem;
    box-shadow: var(--shadow);
    transition: border-color .2s ease, box-shadow .2s ease;
}
.ec-card:hover { border-color: #BFDBFE; box-shadow: 0 2px 4px rgba(37,99,235,.06), 0 10px 24px rgba(37,99,235,.08); }

/* ---------- Badges & pills ---------- */
.ec-badge {
    display: inline-block; padding: 3px 12px; border-radius: 999px;
    font-size: .72rem; font-weight: 600; letter-spacing: .02em;
}
.badge-high     { background: #DCFCE7; color: #15803D; }
.badge-moderate { background: #FEF3C7; color: #B45309; }
.badge-low      { background: #FEE2E2; color: #B91C1C; }
.badge-demo     { background: var(--accent-soft); color: var(--accent-2); }

.ec-pill {
    display: inline-block; background: var(--accent-soft); border: 1px solid #DBEAFE;
    border-radius: 999px; padding: 4px 12px; margin: 2px 4px 2px 0;
    font-size: .78rem; color: var(--accent-2); font-weight: 500;
}

.ec-disclaimer {
    font-size: .74rem; color: var(--muted); border-top: 1px dashed var(--border);
    padding-top: .5rem; margin-top: .5rem;
}

/* ---------- Hero ---------- */
.ec-eyebrow { color: var(--accent); font-weight: 700; font-size: .78rem; letter-spacing: .08em; text-transform: uppercase; }
.ec-hero-title { font-size: 2.3rem; font-weight: 800; color: var(--text); line-height: 1.15; letter-spacing: -.02em; }
.ec-hero-sub { color: var(--muted); font-size: 1.02rem; margin-top: .35rem; max-width: 760px; }

/* ---------- Stat cards ---------- */
.ec-stat { background: var(--surface); border: 1px solid var(--border); border-radius: 16px;
           padding: 1rem 1.2rem; text-align: left; box-shadow: var(--shadow); }
.ec-stat .num { font-size: 1.8rem; font-weight: 800; color: var(--accent); letter-spacing: -.02em; }
.ec-stat .label { font-size: .76rem; color: var(--muted); font-weight: 500; }

/* ---------- Buttons: rounded pills, blue primary ---------- */
.stButton > button, .stDownloadButton > button, .stFormSubmitButton > button, .stLinkButton > a {
    border-radius: 999px !important; font-weight: 600 !important; padding: .45rem 1.3rem !important;
    border: 1px solid var(--border) !important; transition: all .15s ease;
}
.stButton > button[kind="primary"], .stFormSubmitButton > button[kind="primary"], .stDownloadButton > button[kind="primary"] {
    background: var(--accent) !important; color: #fff !important; border: 1px solid var(--accent) !important;
    box-shadow: 0 2px 8px rgba(37,99,235,.25);
}
.stButton > button[kind="primary"]:hover, .stFormSubmitButton > button[kind="primary"]:hover {
    background: var(--accent-2) !important; border-color: var(--accent-2) !important;
}
.stButton > button:hover { border-color: var(--accent) !important; color: var(--accent) !important; }
.stButton > button[kind="primary"]:hover { color: #fff !important; }

/* ---------- Inputs ---------- */
.stTextInput input, .stTextArea textarea, .stNumberInput input, .stDateInput input, .stTimeInput input {
    border-radius: 12px !important;
}
div[data-baseweb="select"] > div { border-radius: 12px !important; }

/* ---------- Sidebar ---------- */
[data-testid="stSidebar"] { background: var(--surface); border-right: 1px solid var(--border); }

/* ---------- Chat ---------- */
.ec-chat-user { background: var(--accent-grad); color: #fff; padding: 10px 16px;
    border-radius: 18px 18px 4px 18px; margin: 8px 0 8px auto; max-width: 78%; font-size: .92rem; width: fit-content; }
.ec-chat-bot { background: var(--surface); border: 1px solid var(--border); padding: 10px 16px;
    border-radius: 18px 18px 18px 4px; margin: 8px 0; max-width: 78%; font-size: .92rem; width: fit-content; }
.ec-chat-emergency { border: 1px solid var(--danger) !important; background: #FEF2F2; }

/* ---------- Moving ticker ---------- */
.ec-ticker { overflow: hidden; white-space: nowrap; background: var(--accent-soft);
    border: 1px solid #DBEAFE; border-radius: 999px; padding: 8px 0; margin: 12px 0 18px 0; }
.ec-ticker-track { display: inline-block; padding-left: 100%; animation: ec-scroll 55s linear infinite; }
.ec-ticker-item { display: inline-block; margin: 0 2.2rem; color: var(--accent-2); font-size: .86rem; font-weight: 500; }
@keyframes ec-scroll { 0% { transform: translateX(0); } 100% { transform: translateX(-100%); } }

/* ---------- Calendar ---------- */
.ec-cal { width: 100%; border-collapse: separate; border-spacing: 4px; }
.ec-cal th { color: var(--muted); font-size: .72rem; font-weight: 600; text-transform: uppercase; padding: 4px; }
.ec-cal td { background: var(--surface); border: 1px solid var(--border); border-radius: 10px; height: 64px;
    vertical-align: top; padding: 5px 7px; font-size: .8rem; }
.ec-cal td.today { border: 2px solid var(--accent); }
.ec-cal td.has-appt { background: var(--accent-soft); }
.ec-cal .dot { display: block; font-size: .66rem; color: var(--accent-2); font-weight: 600; margin-top: 2px; overflow: hidden; text-overflow: ellipsis; }

/* ---------- Diff highlight ---------- */
mark.ec-diff-a { background: #FEE2E2; color: #991B1B; border-radius: 4px; padding: 0 3px; }
mark.ec-diff-b { background: #DBEAFE; color: #1E40AF; border-radius: 4px; padding: 0 3px; }
</style>
"""


def inject():
    st.markdown(CSS, unsafe_allow_html=True)


def hero(title: str, subtitle: str, eyebrow: str | None = None):
    eyebrow_html = f'<div class="ec-eyebrow">{eyebrow}</div>' if eyebrow else ""
    st.markdown(f"""
        <div style="padding:.25rem 0 1.2rem 0;">
            {eyebrow_html}
            <div class="ec-hero-title">{title}</div>
            <div class="ec-hero-sub">{subtitle}</div>
        </div>
    """, unsafe_allow_html=True)


def stat_card(col, number, label):
    with col:
        st.markdown(f"""
            <div class="ec-stat"><div class="num">{number}</div><div class="label">{label}</div></div>
        """, unsafe_allow_html=True)


def badge(label: str, kind: str) -> str:
    return f'<span class="ec-badge badge-{kind}">{label}</span>'


def pill(text: str) -> str:
    return f'<span class="ec-pill">{text}</span>'


def ticker(items: list[str]):
    """Auto-scrolling marquee of health tips (pure CSS, no JS)."""
    spans = "".join(f'<span class="ec-ticker-item">💙 {i}</span>' for i in items)
    st.markdown(f'<div class="ec-ticker"><div class="ec-ticker-track">{spans}</div></div>',
                unsafe_allow_html=True)
