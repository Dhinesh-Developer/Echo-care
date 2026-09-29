"""
EchoCare Agent Orchestrator — a tool-using agent with a small, fixed set of
tools and an explicit (rather than free-form autonomous) routing policy.

Tools available to the agent:
  1. rag_search(query)      -> the patient's own longitudinal evidence (rag.py)
  2. web_search(query)      -> Tavily, for general medical/wellness grounding
  3. department_lookup(txt) -> the trained specialty classifier (ml/)
  4. safety_check(text)     -> Alg. 4 emergency guard — always runs FIRST

Why explicit routing instead of a free-form ReAct loop: in a healthcare
context, an agent that might skip the safety check, hallucinate a tool call,
or loop unpredictably is a liability, not a feature. This orchestrator always
runs safety_check first, always retrieves rag_search, and calls web_search
only when the query needs external grounding (heuristic below) — a
deterministic, auditable policy that still demonstrates real tool selection
and multi-source synthesis.
"""
import re
import llm
import rag
from safety import check_emergency, EMERGENCY_MESSAGE, EMERGENCY_RESOURCES

WEB_GROUNDING_TRIGGERS = re.compile(
    r"\b(latest|research|guideline|recommend|should i|what is|what are|causes of|"
    r"treatment for|how to|tips for|is it normal|normal range|risk factor)\b",
    re.IGNORECASE,
)


def needs_web_grounding(query: str, rag_hits: list[dict]) -> bool:
    return bool(WEB_GROUNDING_TRIGGERS.search(query)) or len(rag_hits) == 0


def run_agent(user_id: int, user_message: str) -> dict:
    """
    Returns {"content": str, "is_emergency": bool, "tools_used": [str],
             "rag_chunk_ids": [str], "web_sources": [dict]}
    """
    # Tool 4: safety_check — always first, non-negotiable
    if check_emergency(user_message):
        return {
            "content": EMERGENCY_MESSAGE, "is_emergency": True,
            "tools_used": ["safety_check"], "rag_chunk_ids": [], "web_sources": [],
            "resources": EMERGENCY_RESOURCES,
        }

    tools_used = ["safety_check"]

    # Tool 1: rag_search — always attempted
    rag_hits = rag.retrieve_for_query(user_id, user_message, top_k=5)
    tools_used.append("rag_search")

    # Tool 2: web_search — only when the query needs external grounding
    web_results = []
    if needs_web_grounding(user_message, rag_hits):
        web_resp = llm.tavily_search(user_message, max_results=3)
        if web_resp["ok"]:
            web_results = web_resp["results"]
            tools_used.append("web_search")

    evidence_block = (
        "\n".join(f"- ({c['source_type']}) {c['text']}" for c in rag_hits)
        or "(no prior evidence on file for this patient yet)"
    )
    web_block = (
        "\n".join(f"- {r['title']}: {r['content'][:200]}" for r in web_results if r.get("content"))
        or "(no web grounding retrieved)"
    )

    prompt = (
        f"Patient's own health history (private, from their records):\n{evidence_block}\n\n"
        f"General web-sourced medical/wellness context (not patient-specific):\n{web_block}\n\n"
        f"Patient says: {user_message}\n\n"
        "Answer using the patient's own history first, and the web context only for general "
        "background if it helps. Do not diagnose. If asked for a diagnosis or treatment plan, "
        "say you're not able to provide that and suggest they discuss it with a clinician."
    )
    result = llm.gemini_generate(prompt)
    if result["ok"]:
        tools_used.append("gemini_generate")
        content = result["text"]
    else:
        reason = (result.get("reason") or "Gemini returned no error details.").strip()
        content = (
            "Echo could not generate a reply. Your message has been saved. "
            f"Gemini error: {reason[:300]}"
        )

    return {
        "content": content, "is_emergency": False, "tools_used": tools_used,
        "rag_chunk_ids": [str(c["id"]) for c in rag_hits], "web_sources": web_results,
    }
