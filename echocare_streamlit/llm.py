"""
The ONLY two external API integrations in this app, per project constraints:
  - Google Gemini (generation)
  - Tavily (web grounding / search)
Both read their keys from Streamlit secrets (.streamlit/secrets.toml) or
environment variables, and every function returns a uniform
{"ok": bool, ...} shape so callers never silently show fabricated content —
an unconfigured/unreachable provider always says so explicitly.
"""
import os
from pathlib import Path

import streamlit as st
from dotenv import dotenv_values, load_dotenv

# Streamlit does not load a project .env file automatically. Load the one next
# to this module so local API keys work with `streamlit run app.py`.
_DOTENV_PATH = Path(__file__).resolve().with_name(".env")
_LOCAL_ENV = dotenv_values(_DOTENV_PATH)
load_dotenv(_DOTENV_PATH)

SYSTEM_PROMPT = (
    "You are EchoCare's clinical-evidence assistant. You NEVER provide a diagnosis, "
    "even implicitly. You only phrase observations as discussion points for the "
    "patient to raise with a licensed clinician. Ground every statement strictly in "
    "the evidence given to you — never use outside medical knowledge to fill gaps. "
    "If evidence is thin, say so plainly. Keep responses concise, warm, and non-alarmist."
)


def _get_key(name: str) -> str:
    # Prefer the project .env so stale values in secrets.toml (or the shell)
    # cannot shadow the configured local API key.
    value = _LOCAL_ENV.get(name)
    if value:
        return str(value).strip()
    value = os.environ.get(name, "")
    if value:
        return value
    try:
        if name in st.secrets:
            return st.secrets[name]
    except Exception:
        pass
    return ""


def gemini_configured() -> bool:
    return bool(_get_key("GOOGLE_API_KEY"))


def tavily_configured() -> bool:
    return bool(_get_key("TAVILY_API_KEY"))


@st.cache_resource(show_spinner=False)
def _gemini_model(api_key: str):
    import google.generativeai as genai
    genai.configure(api_key=api_key)
    return genai.GenerativeModel("gemini-3.8-flash", system_instruction=SYSTEM_PROMPT)


def gemini_generate(prompt: str) -> dict:
    if not gemini_configured():
        return {"ok": False, "text": None, "provider": "gemini",
                "reason": "GOOGLE_API_KEY is not configured in Streamlit secrets."}
    try:
        model = _gemini_model(_get_key("GOOGLE_API_KEY"))
        response = model.generate_content(prompt)
        return {"ok": True, "text": response.text, "provider": "gemini", "reason": None}
    except Exception as e:
        return {"ok": False, "text": None, "provider": "gemini", "reason": str(e)}


def tavily_search(query: str, max_results: int = 3) -> dict:
    if not tavily_configured():
        return {"ok": False, "results": [], "reason": "TAVILY_API_KEY is not configured in Streamlit secrets."}
    try:
        from tavily import TavilyClient
        client = TavilyClient(api_key=_get_key("TAVILY_API_KEY"))
        resp = client.search(query=query, max_results=max_results)
        results = [
            {"title": r.get("title"), "url": r.get("url"), "content": r.get("content")}
            for r in resp.get("results", [])
        ]
        return {"ok": True, "results": results, "reason": None}
    except Exception as e:
        return {"ok": False, "results": [], "reason": str(e)}
