"""
EchoCare Agent Orchestrator: a tool-using agent with an explicit, auditable routing policy.

Tools:
  safety_check   Alg. 4 emergency guard (always FIRST)
  followup       asks for missing duration / severity / trigger before answering (V2)
  rag_search     the patient's own longitudinal evidence (semantic when Gemini is configured)
  web_search     Tavily, only when the question needs external grounding
  gemini_generate  final grounded answer, in the patient's chosen language

Why an explicit policy instead of a free-form ReAct loop: in healthcare, an agent that might skip the
safety check or loop unpredictably is a liability. This one always checks safety first and is deterministic.
"""
import re

import i18n
import llm
import rag
from safety import check_emergency, EMERGENCY_MESSAGE, EMERGENCY_RESOURCES

WEB_GROUNDING_TRIGGERS = re.compile(
    r"\b(latest|research|guideline|recommend|should i|what is|what are|causes of|treatment for|"
    r"how to|tips for|is it normal|normal range|risk factor)\b", re.IGNORECASE)

DETAIL_PATTERNS = {
    "duration": re.compile(r"\b(\d+\s*(day|days|week|weeks|month|months|year|years|hour|hours)|since|for a (day|week|month|year)|"
                           r"yesterday|last night|few (days|weeks|months)|days|weeks|months)\b", re.I),
    "severity": re.compile(r"\b(\d{1,2}\s*/\s*10|\d{1,2} out of 10|mild|moderate|severe|unbearable|slight|worst|terrible)\b", re.I),
    "trigger": re.compile(r"\b(after|before|when|while|during|triggered|worse|better|morning|evening|night|eating|exercise|"
                          r"walking|stress|lying|standing|food)\b", re.I),
}
QUESTION_KEYS = {"duration": "q_duration", "severity": "q_severity", "trigger": "q_trigger"}


def needs_web_grounding(query: str, rag_hits: list[dict]) -> bool:
    return bool(WEB_GROUNDING_TRIGGERS.search(query)) or len(rag_hits) == 0


def missing_details(text: str) -> list[str]:
    return [k for k, pat in DETAIL_PATTERNS.items() if not pat.search(text)]


def followup_questions(message: str, history: list[dict] | None) -> list[str] | None:
    """Ask follow-ups only for a NEW symptom message that lacks detail, and never twice in a row."""
    history = history or []
    last_assistant = next((m for m in reversed(history) if m["role"] == "assistant"), None)
    if last_assistant and last_assistant.get("kind") == "followup":
        return None  # the user is answering our questions: proceed to a real answer
    if rag.tag_themes(message) == ["general_wellbeing"]:
        return None
    if WEB_GROUNDING_TRIGGERS.search(message) and "?" in message:
        return None  # a general knowledge question, not a symptom report
    missing = missing_details(message)
    return missing if len(missing) >= 2 else None


def _history_block(history: list[dict] | None, limit: int = 6) -> str:
    if not history:
        return "(this is the start of the conversation)"
    return "\n".join(f"{m['role']}: {m['content']}" for m in history[-limit:])


def run_agent(user_id: int, user_message: str, history: list[dict] | None = None) -> dict:
    # Tool: safety_check, always first
    if check_emergency(user_message):
        return {"content": EMERGENCY_MESSAGE, "is_emergency": True, "tools_used": ["safety_check"],
                "rag_chunk_ids": [], "web_sources": [], "resources": EMERGENCY_RESOURCES, "kind": None}

    tools_used = ["safety_check"]

    # Tool: followup
    missing = followup_questions(user_message, history)
    if missing:
        qs = "\n".join(f"{i}. {i18n.t(QUESTION_KEYS[k])}" for i, k in enumerate(missing, 1))
        return {"content": f"{i18n.t('followup_intro')}\n{qs}", "is_emergency": False,
                "tools_used": tools_used + ["followup"], "rag_chunk_ids": [], "web_sources": [],
                "kind": "followup"}

    # Tool: rag_search, using the conversation so an answer to a follow-up keeps its context
    last_user = next((m["content"] for m in reversed(history or []) if m["role"] == "user"), "")
    query = f"{last_user} {user_message}".strip() if history and history[-1].get("kind") == "followup" else user_message
    rag_hits = rag.retrieve_for_query(user_id, query, top_k=5)
    tools_used.append("rag_search")

    # Tool: web_search, only when needed
    web_results = []
    if needs_web_grounding(query, rag_hits):
        resp = llm.tavily_search(query, max_results=3)
        if resp["ok"]:
            web_results = resp["results"]
            tools_used.append("web_search")

    evidence = "\n".join(f"- ({c['source_type']}) {c['text']}" for c in rag_hits) or "(no prior evidence on file yet)"
    web = "\n".join(f"- {r['title']}: {r['content'][:200]}" for r in web_results if r.get("content")) or "(none)"
    prompt = (f"Conversation so far:\n{_history_block(history)}\n\n"
              f"Patient's own health history (private records):\n{evidence}\n\n"
              f"General web context (not patient-specific):\n{web}\n\n"
              f"Patient says: {user_message}\n\n"
              "Answer using the patient's own history first; use web context only for general background. "
              "Do not diagnose. If asked for a diagnosis or treatment plan, say you can't provide one and "
              "suggest discussing it with a clinician.")
    result = llm.gemini_generate(prompt)
    if result["ok"]:
        tools_used.append("gemini_generate")
        content = result["text"]
    else:
        reason = result.get("reason") or "Gemini did not return a response."
        content = f"Echo couldn't generate a reply: {reason} Your message is saved."
    return {"content": content, "is_emergency": False, "tools_used": tools_used,
            "rag_chunk_ids": [str(c["id"]) for c in rag_hits], "web_sources": web_results, "kind": None}
