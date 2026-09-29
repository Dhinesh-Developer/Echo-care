"""
Alg. 3 — LE-RAG (Longitudinal Evidence RAG), lightweight edition.

Uses TF-IDF (scikit-learn) instead of a neural embedding model. This is a
deliberate engineering trade-off for this deployment target: Streamlit
Community Cloud's free tier has ~1GB RAM, and a transformer embedding model
(even a "small" one) plus its torch/sentence-transformers dependencies
regularly blows that budget and causes silent crashes on deploy. TF-IDF is
zero-download, sub-millisecond, and — for the terse symptom/health-log text
this app deals with — retrieves comparably well. Swap in
sentence-transformers by replacing `_fit_vectorizer` / `_similarity` if you
deploy somewhere with more headroom (see README).
"""
import re
from datetime import datetime
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity as sk_cosine

import db
from specialties import KEYWORD_TO_SPECIALTY

MIN_OCCURRENCES = 2
MIN_DISTINCT_SOURCES = 2
CONFIDENCE_THRESHOLD = 0.4

W_SIMILARITY = 0.4
W_SOURCE_DIVERSITY = 0.25
W_OCCURRENCE_RATE = 0.2
W_TEMPORAL_CONSISTENCY = 0.15

TIMELINE_PATTERN = re.compile(
    r"\b(for|since|over the (last|past))\s+(the\s+)?(\d+\s*(day|days|week|weeks|month|months|year|years)|"
    r"few\s+(days|weeks|months)|a\s+(day|week|month|year))\b",
    re.IGNORECASE,
)


def extract_timeline(text: str) -> str | None:
    match = TIMELINE_PATTERN.search(text)
    return match.group(0) if match else None


def tag_themes(text: str) -> list[str]:
    """Alg. 1 — lightweight NLP/NER: keyword-spot against the SPECIALTIES map."""
    text_l = text.lower()
    matched = {specialty for kw, specialty in KEYWORD_TO_SPECIALTY.items() if kw in text_l}
    return sorted(matched) or ["general_wellbeing"]


def _chunk_text(text: str, max_len: int = 260) -> list[str]:
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    chunks, buf = [], ""
    for s in sentences:
        if len(buf) + len(s) <= max_len:
            buf = f"{buf} {s}".strip()
        else:
            if buf:
                chunks.append(buf)
            buf = s
    if buf:
        chunks.append(buf)
    return chunks or [text]


def chunk_and_store(user_id: int, source_type: str, text: str, metadata: dict | None = None):
    if not text or not text.strip():
        return
    for piece in _chunk_text(text):
        db.insert_evidence_chunk(user_id, source_type, piece, tag_themes(piece), metadata)


def _fit_and_search(corpus_texts: list[str], query: str, top_k: int = 6) -> list[tuple[int, float]]:
    """Returns [(index_in_corpus, similarity_score), ...] sorted descending."""
    if not corpus_texts:
        return []
    vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
    try:
        matrix = vectorizer.fit_transform(corpus_texts + [query])
    except ValueError:
        return []  # corpus was all stopwords / empty after vectorization
    query_vec = matrix[-1]
    corpus_matrix = matrix[:-1]
    sims = sk_cosine(query_vec, corpus_matrix)[0]
    ranked = sorted(enumerate(sims), key=lambda x: x[1], reverse=True)
    return ranked[:top_k]


def _composite_confidence(sims: list[float], source_types: set, occurrence_count: int, span_days: int) -> float:
    if not sims:
        return 0.0
    avg_sim = sum(sims) / len(sims)
    source_diversity = min(len(source_types) / 4, 1.0)
    occurrence_rate = min(occurrence_count / 8, 1.0)
    temporal_consistency = min(span_days / 21, 1.0) if span_days else 0.25
    score = (
        W_SIMILARITY * avg_sim + W_SOURCE_DIVERSITY * source_diversity
        + W_OCCURRENCE_RATE * occurrence_rate + W_TEMPORAL_CONSISTENCY * temporal_consistency
    )
    return round(min(score, 1.0), 3)


def _confidence_label(score: float) -> str:
    if score >= 0.65:
        return "high"
    if score >= CONFIDENCE_THRESHOLD:
        return "moderate"
    return "low"


def generate_insights(user_id: int, generate_fn) -> list[dict]:
    """
    generate_fn(prompt: str) -> dict {"ok": bool, "text": str|None, "provider": str}
    is injected so this module has zero direct dependency on the Gemini SDK
    (keeps it testable and keeps the provider swap in one place: llm.py).
    """
    chunks = db.get_evidence_chunks(user_id)
    if not chunks:
        return []

    themes: dict[str, list[dict]] = {}
    for c in chunks:
        for t in c["theme_tags"]:
            themes.setdefault(t, []).append(c)

    insights = []
    for theme, theme_chunks in themes.items():
        if theme == "general_wellbeing":
            continue
        distinct_sources = {c["source_type"] for c in theme_chunks}
        if len(theme_chunks) < MIN_OCCURRENCES or len(distinct_sources) < MIN_DISTINCT_SOURCES:
            continue  # evidence-sufficiency gate — never bypassed to look impressive

        corpus = [c["text"] for c in theme_chunks]
        ranked = _fit_and_search(corpus, theme.replace("_", " "), top_k=6)
        if not ranked:
            continue
        retrieved = [theme_chunks[i] for i, _ in ranked]
        sims = [s for _, s in ranked]

        timestamps = [datetime.fromisoformat(c["timestamp"]) for c in theme_chunks]
        span_days = (max(timestamps) - min(timestamps)).days if len(timestamps) > 1 else 0

        evidence_text = "\n".join(f"- ({c['source_type']}) {c['text']}" for c in retrieved)
        prompt = (
            f"Patient evidence relevant to '{theme}':\n{evidence_text}\n\n"
            "Write a short (2-3 sentence), non-diagnostic observation the patient could raise "
            "with their doctor, based ONLY on the evidence above. Never name a disease. "
            "Never add outside medical knowledge not present in the evidence."
        )
        result = generate_fn(prompt)

        source_counts: dict[str, int] = {}
        for c in retrieved:
            source_counts[c["source_type"]] = source_counts.get(c["source_type"], 0) + 1

        confidence = _composite_confidence(sims, distinct_sources, len(theme_chunks), span_days)
        insights.append({
            "theme": theme,
            "text": result["text"] if result["ok"] else (
                "Insight text is temporarily unavailable (Gemini not configured/reachable). "
                "Your evidence has still been recorded."
            ),
            "confidence": confidence,
            "confidence_label": _confidence_label(confidence),
            "evidence_summary": "based on: " + ", ".join(f"{v} {k}" for k, v in source_counts.items()),
            "evidence_chunk_ids": [str(c["id"]) for c in retrieved],
            "generated_by": result["provider"] if result["ok"] else "unavailable",
            "generation_error": result.get("reason") if not result["ok"] else None,
        })
    return insights


def retrieve_for_query(user_id: int, query: str, top_k: int = 5) -> list[dict]:
    """Used by the Echo Companion chat agent to ground its answers."""
    chunks = db.get_evidence_chunks(user_id)
    if not chunks:
        return []
    corpus = [c["text"] for c in chunks]
    ranked = _fit_and_search(corpus, query, top_k=top_k)
    return [chunks[i] for i, _ in ranked]
