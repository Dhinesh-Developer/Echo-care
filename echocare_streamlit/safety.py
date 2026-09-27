"""
Alg. 4 — Safety / Emergency Escalation Guard.
Runs BEFORE any narrative or chat text reaches an LLM or is stored as normal
evidence. If matched, the caller must short-circuit the normal flow and show
emergency resources instead of proceeding.
"""
import re

EMERGENCY_PATTERNS = [
    r"\bsuicid\w*\b", r"\bkill myself\b", r"\bend my life\b", r"\bwant to die\b",
    r"\bself[- ]harm\w*\b", r"\bchest pain\b", r"\bcan'?t breathe\b",
    r"\btrouble breathing\b", r"\bsevere bleeding\b", r"\bunconscious\b",
    r"\bstroke\b.*\b(face|arm|speech)\b", r"\boverdose\b", r"\banaphylax\w*\b",
    r"\bheart attack\b",
]
_compiled = [re.compile(p, re.IGNORECASE) for p in EMERGENCY_PATTERNS]

EMERGENCY_MESSAGE = (
    "This may describe a medical or mental health emergency. EchoCare cannot help "
    "in real time. Please contact emergency services or a crisis line right away."
)

EMERGENCY_RESOURCES = [
    ("Emergency services (India)", "112"),
    ("iCall Psychosocial Helpline (India)", "+91 9152987821"),
    ("Emergency services (US)", "911"),
    ("988 Suicide & Crisis Lifeline (US)", "call or text 988"),
    ("Outside India/US", "search 'emergency number' + your country, or go to the nearest ER"),
]


def check_emergency(text: str) -> bool:
    if not text:
        return False
    return any(p.search(text) for p in _compiled)
