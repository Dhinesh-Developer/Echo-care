"""
Shared CSS injected on every page — a takeUforward.org-inspired design system:
dark navy background, bold orange/amber accent, card-based sections with soft
borders and glow, gradient CTA buttons, bold sans-serif headers.
"""
import streamlit as st

CSS = """
<style>
:root {
    --bg: #0B0F19;
    --surface: #141A2A;
    --surface-2: #1B2236;
    --border: #232B40;
    --accent: #FF8C1A;
    --accent-2: #FFB347;
    --accent-grad: linear-gradient(135deg, #FF8C1A 0%, #FF5F6D 100%);
    --text: #F1F3F6;
    --muted: #92A0B8;
    --success: #22C55E;
    --warn: #FBBF24;
    --danger: #F87171;
}

.stApp {
    background: var(--bg);
    color: var(--text);
}

/* Card component */
.tuf-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 1.25rem 1.4rem;
    margin-bottom: 1rem;
    box-shadow: 0 4px 18px rgba(0,0,0,0.25);
    transition: border-color .2s ease;
}
.tuf-card:hover { border-color: var(--accent); }

.tuf-badge {
    display: inline-block;
    padding: 3px 12px;
    border-radius: 999px;
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: .02em;
}
.badge-high   { background: rgba(34,197,94,.15); color: var(--success); }
.badge-moderate { background: rgba(251,191,36,.15); color: var(--warn); }
.badge-low    { background: rgba(248,113,113,.15); color: var(--danger); }
.badge-demo   { background: rgba(255,140,26,.15); color: var(--accent); }

.tuf-gradient-btn button {
    background: var(--accent-grad) !important;
    color: #0B0F19 !important;
    font-weight: 700 !important;
    border: none !important;
    border-radius: 10px !important;
}

.tuf-pill {
    display: inline-block;
    background: var(--surface-2);
    border: 1px solid var(--border);
    border-radius: 999px;
    padding: 4px 12px;
    margin: 2px 4px 2px 0;
    font-size: 0.78rem;
    color: var(--accent-2);
}

.tuf-disclaimer {
    font-size: 0.72rem;
    color: var(--muted);
    border-top: 1px dashed var(--border);
    padding-top: 0.5rem;
    margin-top: 0.5rem;
}

.tuf-hero-title {
    font-size: 2.4rem;
    font-weight: 800;
    background: var(--accent-grad);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    line-height: 1.15;
}
.tuf-hero-sub { color: var(--muted); font-size: 1.05rem; margin-top: .25rem; }

.tuf-stat {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 1rem 1.2rem;
    text-align: center;
}
.tuf-stat .num { font-size: 1.8rem; font-weight: 800; color: var(--accent); }
.tuf-stat .label { font-size: .78rem; color: var(--muted); text-transform: uppercase; letter-spacing: .04em; }

/* Sidebar */
[data-testid="stSidebar"] {
    background: var(--surface);
    border-right: 1px solid var(--border);
}

/* Chat bubbles */
.tuf-chat-user {
    background: var(--accent-grad);
    color: #0B0F19;
    padding: 10px 14px;
    border-radius: 14px 14px 2px 14px;
    margin: 6px 0;
    max-width: 78%;
    margin-left: auto;
    font-size: .9rem;
    font-weight: 600;
}
.tuf-chat-bot {
    background: var(--surface-2);
    border: 1px solid var(--border);
    padding: 10px 14px;
    border-radius: 14px 14px 14px 2px;
    margin: 6px 0;
    max-width: 78%;
    font-size: .9rem;
}
.tuf-chat-emergency { border: 1px solid var(--danger) !important; }

/* Slideshow container fade */
.tuf-slide-caption {
    position: absolute;
    bottom: 18px;
    left: 24px;
    color: white;
    font-weight: 700;
    font-size: 1.3rem;
    text-shadow: 0 2px 10px rgba(0,0,0,.6);
}
</style>
"""


def inject():
    st.markdown(CSS, unsafe_allow_html=True)


def hero(title: str, subtitle: str):
    st.markdown(f"""
        <div style="padding:.5rem 0 1.2rem 0;">
            <div class="tuf-hero-title">{title}</div>
            <div class="tuf-hero-sub">{subtitle}</div>
        </div>
    """, unsafe_allow_html=True)


def stat_card(col, number, label):
    with col:
        st.markdown(f"""
            <div class="tuf-stat"><div class="num">{number}</div><div class="label">{label}</div></div>
        """, unsafe_allow_html=True)


def badge(label: str, kind: str) -> str:
    return f'<span class="tuf-badge badge-{kind}">{label}</span>'


def pill(text: str) -> str:
    return f'<span class="tuf-pill">{text}</span>'
