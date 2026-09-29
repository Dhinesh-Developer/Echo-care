"""
The ONLY two external APIs in this app: Google Gemini and Tavily.

Gemini is used through the current `google-genai` SDK for:
  text generation, multimodal reading (images/PDF pages), audio transcription,
  and embeddings (gemini-embedding-001).
Every function returns a uniform {"ok": bool, ...} shape, so an unconfigured or
unreachable provider is reported honestly and never replaced with fake content.
Keys come from Streamlit secrets or environment variables.
"""
import os
import time
import streamlit as st
import i18n
from config import get_secret

SYSTEM_PROMPT = (
    "You are EchoCare's clinical-evidence assistant. You NEVER provide a diagnosis, even implicitly. "
    "You only phrase observations as discussion points for the patient to raise with a licensed "
    "clinician. Ground every statement strictly in the evidence given to you; never use outside medical "
    "knowledge to fill gaps. If evidence is thin, say so plainly. Keep responses concise, warm and non-alarmist."
)

DEFAULT_GEN_MODELS = ["gemini-3.8-flash", "gemini-3.7-flash", "gemini-3.5-flash"]
DEFAULT_EMBED_MODEL = "gemini-embedding-001"


def _provider_error(exc: Exception) -> str:
    """Return actionable provider errors without dumping a verbose SDK response."""
    message = str(exc)
    normalized = message.upper()
    if "API_KEY_INVALID" in normalized or "API KEY NOT VALID" in normalized:
        return (
            "Google rejected the configured GOOGLE_API_KEY. Replace it with a valid "
            "Gemini API key from Google AI Studio in .streamlit/secrets.toml, then "
            "restart Streamlit. The .example file is only a template."
        )
    if "503" in normalized or "UNAVAILABLE" in normalized or "HIGH DEMAND" in normalized:
        return "Gemini is temporarily busy. Echo tried its fallback models; please send your message again in a moment."
    if "429" in normalized or "RESOURCE_EXHAUSTED" in normalized:
        return "Gemini's request limit was reached. Please wait a moment and try again."
    return message


def _get_key(name: str, default: str = "") -> str:
    return get_secret(name, default)


def gemini_configured() -> bool:
    return bool(_get_key("GOOGLE_API_KEY"))


def tavily_configured() -> bool:
    return bool(_get_key("TAVILY_API_KEY"))


@st.cache_resource(show_spinner=False)
def _client(api_key: str):
    from google import genai
    return genai.Client(api_key=api_key)


def _gen_models() -> list[str]:
    configured = _get_key("GEMINI_MODEL")
    return ([configured] if configured else []) + [m for m in DEFAULT_GEN_MODELS if m != configured]


def _language_instruction(language: str | None) -> str:
    lang = language or i18n.lang_name()
    return "" if lang == "English" else f"\n\nRespond entirely in {lang} (keep medical terms understandable)."


def _generate(contents, system: str, language: str | None = None, json_mode: bool = False) -> dict:
    if not gemini_configured():
        return {"ok": False, "text": None, "provider": "gemini",
                "reason": "GOOGLE_API_KEY is not configured in Streamlit secrets."}
    try:
        from google.genai import types
        client = _client(_get_key("GOOGLE_API_KEY"))
        cfg = types.GenerateContentConfig(
            system_instruction=system + _language_instruction(language),
            response_mime_type="application/json" if json_mode else None,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True))
        last_err = None
        for model in _gen_models():
            for attempt in range(2):
                try:
                    resp = client.models.generate_content(model=model, contents=contents, config=cfg)
                    return {"ok": True, "text": resp.text, "provider": f"gemini ({model})", "reason": None}
                except Exception as e:  # retry temporary overload once, then try the next fallback model
                    last_err = e
                    normalized = str(e).upper()
                    transient = any(marker in normalized for marker in
                                    ("503", "UNAVAILABLE", "HIGH DEMAND", "429", "RESOURCE_EXHAUSTED"))
                    if attempt == 0 and transient:
                        time.sleep(0.5)
                        continue
                    break
        return {"ok": False, "text": None, "provider": "gemini", "reason": _provider_error(last_err)}
    except Exception as e:
        return {"ok": False, "text": None, "provider": "gemini", "reason": _provider_error(e)}


def gemini_generate(prompt: str, system: str = SYSTEM_PROMPT, language: str | None = None) -> dict:
    return _generate(prompt, system, language)


def gemini_generate_json(prompt: str, parts: list | None = None, system: str = SYSTEM_PROMPT) -> dict:
    """Multimodal-friendly JSON extraction. parts = [(bytes, mime_type), ...] placed before the prompt."""
    contents = []
    if parts:
        from google.genai import types
        contents += [types.Part.from_bytes(data=b, mime_type=m) for b, m in parts]
    contents.append(prompt)
    return _generate(contents, system, language="English", json_mode=True)


def gemini_vision(parts: list, prompt: str, language: str | None = None) -> dict:
    """Free-text answer about images / PDF pages. parts = [(bytes, mime_type), ...]."""
    if not gemini_configured():
        return _generate(prompt, SYSTEM_PROMPT)  # returns the standard 'not configured' result
    from google.genai import types
    contents = [types.Part.from_bytes(data=b, mime_type=m) for b, m in parts] + [prompt]
    return _generate(contents, SYSTEM_PROMPT, language)


def gemini_transcribe(audio_bytes: bytes, mime_type: str = "audio/wav") -> dict:
    prompt = ("Transcribe this audio exactly as spoken. The speaker may use English, Tamil or Hindi. "
              "Return only the transcript text, in the language spoken, with no commentary.")
    if not gemini_configured():
        return _generate(prompt, SYSTEM_PROMPT)
    from google.genai import types
    contents = [types.Part.from_bytes(data=audio_bytes, mime_type=mime_type), prompt]
    return _generate(contents, "You are a precise speech transcriber.", language="English")


def embeddings_available() -> bool:
    return gemini_configured()


def gemini_embed(texts: list[str], task_type: str = "RETRIEVAL_DOCUMENT") -> list[list[float]] | None:
    """Returns one vector per input text, or None if unavailable/failed (callers fall back to TF-IDF)."""
    if not texts or not gemini_configured():
        return None
    try:
        from google.genai import types
        client = _client(_get_key("GOOGLE_API_KEY"))
        model = _get_key("EMBED_MODEL", DEFAULT_EMBED_MODEL)
        resp = client.models.embed_content(
            model=model, contents=list(texts),
            config=types.EmbedContentConfig(task_type=task_type, output_dimensionality=768))
        vectors = [list(e.values) for e in resp.embeddings]
        if len(vectors) != len(texts):  # defensive: never mis-align embeddings with chunks
            vectors = []
            for t in texts:
                r = client.models.embed_content(
                    model=model, contents=t,
                    config=types.EmbedContentConfig(task_type=task_type, output_dimensionality=768))
                vectors.append(list(r.embeddings[0].values))
        return vectors
    except Exception:
        return None


def tavily_search(query: str, max_results: int = 3) -> dict:
    if not tavily_configured():
        return {"ok": False, "results": [], "reason": "TAVILY_API_KEY is not configured in Streamlit secrets."}
    try:
        from tavily import TavilyClient
        client = TavilyClient(api_key=_get_key("TAVILY_API_KEY"))
        resp = client.search(query=query, max_results=max_results)
        results = [{"title": r.get("title"), "url": r.get("url"), "content": r.get("content")}
                   for r in resp.get("results", [])]
        return {"ok": True, "results": results, "reason": None}
    except Exception as e:
        return {"ok": False, "results": [], "reason": str(e)}
