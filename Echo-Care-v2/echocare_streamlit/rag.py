"""
Alg. 3: LE-RAG (Longitudinal Evidence RAG), V2 edition.

Retrieval is SEMANTIC when Gemini is configured: every evidence chunk is embedded
with gemini-embedding-001 (stored in SQLite) and retrieved by cosine similarity, so
"my head throbs" matches "migraine" without sharing a keyword. If Gemini is not
configured or fails, retrieval falls back to TF-IDF, so the app always works, and every
insight records which method produced it.
"""
import re
from datetime import datetime

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity as sk_cosine

import db
import llm
from specialties import KEYWORD_TO_SPECIALTY, SPECIALTIES

MIN_OCCURRENCES = 2
MIN_DISTINCT_SOURCES = 2
CONFIDENCE_THRESHOLD = 0.4

W_SIMILARITY = 0.4
W_SOURCE_DIVERSITY = 0.25
W_OCCURRENCE_RATE = 0.2
W_TEMPORAL_CONSISTENCY = 0.15

TIMELINE_PATTERN = re.compile(
    r"\b(for|since|over the (last|past))\s+(the\s+)?(\d+\s*(day|days|week|weeks|month|months|year|years)|"
    r"few\s+(days|weeks|months)|a\s+(day|week|month|year))\b", re.IGNORECASE)


def extract_timeline(text: str) -> str | None:
    match = TIMELINE_PATTERN.search(text)
    return match.group(0) if match else None


def tag_themes(text: str) -> list[str]:
    """Alg. 1: keyword-spot against the SPECIALTIES map."""
    text_l = text.lower()
    matched = {sp for kw, sp in KEYWORD_TO_SPECIALTY.items() if kw in text_l}
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
    pieces = _chunk_text(text)
    vectors = llm.gemini_embed(pieces, "RETRIEVAL_DOCUMENT") if llm.embeddings_available() else None
    for i, piece in enumerate(pieces):
        emb = vectors[i] if vectors and i < len(vectors) else None
        db.insert_evidence_chunk(user_id, source_type, piece, tag_themes(piece), metadata, emb)


def backfill_embeddings(user_id: int, limit: int = 100) -> int:
    """Embeds older chunks that were saved before Gemini was configured."""
    if not llm.embeddings_available():
        return 0
    missing = [c for c in db.get_evidence_chunks(user_id) if not c["embedding"]][:limit]
    if not missing:
        return 0
    vectors = llm.gemini_embed([c["text"] for c in missing], "RETRIEVAL_DOCUMENT")
    if not vectors:
        return 0
    for c, v in zip(missing, vectors):
        db.update_chunk_embedding(c["id"], v)
    return len(missing)


def _tfidf_search(corpus: list[str], query: str, top_k: int) -> list[tuple[int, float]]:
    if not corpus:
        return []
    try:
        matrix = TfidfVectorizer(stop_words="english", ngram_range=(1, 2)).fit_transform(corpus + [query])
    except ValueError:
        return []
    sims = sk_cosine(matrix[-1], matrix[:-1])[0]
    return sorted(enumerate(sims), key=lambda x: x[1], reverse=True)[:top_k]


# kept for backwards compatibility with earlier tests/pages
_fit_and_search = _tfidf_search


def search_chunks(chunks: list[dict], query: str, top_k: int = 6) -> tuple[list[tuple[dict, float]], str]:
    """Returns ([(chunk, similarity)...], method) where method is 'semantic' or 'keyword'."""
    if not chunks:
        return [], "keyword"
    embedded = [c for c in chunks if c.get("embedding")]
    if llm.embeddings_available() and len(embedded) >= max(1, int(0.8 * len(chunks))):
        qv = llm.gemini_embed([query], "RETRIEVAL_QUERY")
        if qv:
            q = np.array(qv[0], dtype=float)
            matrix = np.array([c["embedding"] for c in embedded], dtype=float)
            denom = np.linalg.norm(matrix, axis=1) * (np.linalg.norm(q) or 1.0)
            sims = matrix @ q / np.where(denom == 0, 1.0, denom)
            order = np.argsort(-sims)[:top_k]
            return [(embedded[i], float(sims[i])) for i in order], "semantic"
    ranked = _tfidf_search([c["text"] for c in chunks], query, top_k)
    return [(chunks[i], float(s)) for i, s in ranked], "keyword"


def _composite_confidence(sims: list[float], source_types: set, occurrence_count: int, span_days: int):
    """Returns (score, breakdown) so the UI can explain exactly how confidence was computed."""
    if not sims:
        return 0.0, {}
    parts = {
        "similarity": max(0.0, min(sum(sims) / len(sims), 1.0)),
        "source_diversity": min(len(source_types) / 4, 1.0),
        "occurrence_rate": min(occurrence_count / 8, 1.0),
        "temporal_consistency": min(span_days / 21, 1.0) if span_days else 0.25,
    }
    score = (W_SIMILARITY * parts["similarity"] + W_SOURCE_DIVERSITY * parts["source_diversity"]
             + W_OCCURRENCE_RATE * parts["occurrence_rate"] + W_TEMPORAL_CONSISTENCY * parts["temporal_consistency"])
    return round(min(score, 1.0), 3), {k: round(v, 3) for k, v in parts.items()}


def _confidence_label(score: float) -> str:
    return "high" if score >= 0.65 else "moderate" if score >= CONFIDENCE_THRESHOLD else "low"


def generate_insights(user_id: int, generate_fn) -> list[dict]:
    """generate_fn(prompt) -> {"ok","text","provider"}; injected so this module stays provider-agnostic."""
    backfill_embeddings(user_id)
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
            continue  # evidence-sufficiency gate, never bypassed

        query = f"{theme}: " + ", ".join(SPECIALTIES.get(theme, [])[:6])
        hits, method = search_chunks(theme_chunks, query, top_k=6)
        if not hits:
            continue
        retrieved = [c for c, _ in hits]
        sims = [max(s, 0.0) for _, s in hits]

        stamps = [datetime.fromisoformat(c["timestamp"]) for c in theme_chunks]
        span_days = (max(stamps) - min(stamps)).days if len(stamps) > 1 else 0

        evidence_text = "\n".join(f"- ({c['source_type']}) {c['text']}" for c in retrieved)
        prompt = (f"Patient evidence relevant to '{theme}':\n{evidence_text}\n\n"
                  "Write a short (2-3 sentence), non-diagnostic observation the patient could raise with their "
                  "doctor, based ONLY on the evidence above. Never name a disease. Never add outside medical knowledge.")
        result = generate_fn(prompt)

        counts: dict[str, int] = {}
        for c in retrieved:
            counts[c["source_type"]] = counts.get(c["source_type"], 0) + 1
        confidence, breakdown = _composite_confidence(sims, distinct_sources, len(theme_chunks), span_days)
        breakdown["retrieval"] = "semantic (Gemini embeddings)" if method == "semantic" else "keyword (TF-IDF)"
        insights.append({
            "theme": theme,
            "text": result["text"] if result["ok"] else (
                "Insight text is unavailable right now (Gemini not configured or unreachable). "
                "Your evidence is recorded and can be reviewed below."),
            "confidence": confidence,
            "confidence_label": _confidence_label(confidence),
            "evidence_summary": "based on: " + ", ".join(f"{v} {k}" for k, v in counts.items()),
            "evidence_chunk_ids": [str(c["id"]) for c in retrieved],
            "generated_by": result["provider"] if result["ok"] else "unavailable",
            "confidence_breakdown": breakdown,
        })
    return insights


def retrieve_for_query(user_id: int, query: str, top_k: int = 5) -> list[dict]:
    """Used by the Echo agent to ground answers in the patient's own evidence."""
    hits, _ = search_chunks(db.get_evidence_chunks(user_id), query, top_k)
    return [c for c, _ in hits]
