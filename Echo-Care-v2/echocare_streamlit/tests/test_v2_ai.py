"""V2: Gemini embeddings (semantic RAG), Vision/voice plumbing, multilingual, follow-ups, explainability."""
import hashlib
import re
import types

import numpy as np
import pytest

import agent, db, i18n, labs, llm, rag


def fake_embed(texts, task_type="RETRIEVAL_DOCUMENT"):
    """Deterministic bag-of-words embedding: similar words => similar vectors (a stand-in for Gemini)."""
    out = []
    for t in texts:
        v = np.zeros(64)
        for w in re.findall(r"[a-z]+", t.lower()):
            v[int(hashlib.md5(w.encode()).hexdigest(), 16) % 64] += 1
        out.append(list(v))
    return out


@pytest.fixture
def semantic(monkeypatch):
    monkeypatch.setattr(llm, "embeddings_available", lambda: True)
    monkeypatch.setattr(llm, "gemini_embed", fake_embed)


def test_embeddings_stored_and_semantic_retrieval_used(user, semantic):
    rag.chunk_and_store(user["id"], "narrative", "I get chest tightness when I climb stairs.")
    rag.chunk_and_store(user["id"], "tracker", "Slept 8 hours and drank water.")
    chunks = db.get_evidence_chunks(user["id"])
    assert all(c["embedding"] and len(c["embedding"]) == 64 for c in chunks)
    hits, method = rag.search_chunks(chunks, "chest tightness stairs", top_k=2)
    assert method == "semantic" and "chest" in hits[0][0]["text"]


def test_falls_back_to_tfidf_without_gemini(user):
    rag.chunk_and_store(user["id"], "narrative", "Persistent cough and wheezing at night.")
    chunks = db.get_evidence_chunks(user["id"])
    assert chunks[0]["embedding"] is None
    _, method = rag.search_chunks(chunks, "cough", top_k=1)
    assert method == "keyword"


def test_backfill_embeds_old_chunks(user, monkeypatch):
    rag.chunk_and_store(user["id"], "narrative", "Old chunk saved before the key existed.")
    monkeypatch.setattr(llm, "embeddings_available", lambda: True)
    monkeypatch.setattr(llm, "gemini_embed", fake_embed)
    assert rag.backfill_embeddings(user["id"]) == 1
    assert db.get_evidence_chunks(user["id"])[0]["embedding"]


def test_insights_are_explainable(user, semantic):
    for txt, src in [("Chest pain and palpitations on stairs.", "narrative"), ("Racing heartbeat lately.", "survey"), ("Palpitations at night.", "tracker")]:
        rag.chunk_and_store(user["id"], src, txt)
    ins = rag.generate_insights(user["id"], lambda p: {"ok": True, "text": "Discuss palpitations.", "provider": "fake"})
    cardio = next(i for i in ins if i["theme"] == "Cardiology")
    assert set(cardio["confidence_breakdown"]) >= {"similarity", "source_diversity", "occurrence_rate", "temporal_consistency", "retrieval"}
    assert "semantic" in cardio["confidence_breakdown"]["retrieval"]
    db.insert_insight(user["id"], cardio)
    stored = db.get_insights(user["id"])[0]
    evidence = db.get_evidence_chunks_by_ids(user["id"], stored["evidence_chunk_ids"])
    assert len(evidence) == len(stored["evidence_chunk_ids"]) > 0


def test_evidence_gate_blocks_thin_evidence(user):
    rag.chunk_and_store(user["id"], "narrative", "I have joint pain in my knee.")
    assert rag.generate_insights(user["id"], lambda p: {"ok": False, "text": None, "provider": "x"}) == []


# ---------- follow-up questions ----------
def test_followup_asked_for_vague_symptom_then_not_twice(user):
    r1 = agent.run_agent(user["id"], "I have a headache", [])
    assert r1["kind"] == "followup" and "followup" in r1["tools_used"]
    hist = [{"role": "user", "content": "I have a headache"}, {"role": "assistant", "content": r1["content"], "kind": "followup"}]
    r2 = agent.run_agent(user["id"], "since 3 days, about 6/10, worse in the evening", hist)
    assert r2["kind"] is None


def test_no_followup_when_detail_given_or_not_a_symptom(user):
    assert agent.followup_questions("Severe headache for 3 days after eating", []) is None
    assert agent.followup_questions("What is a normal blood sugar range?", []) is None


def test_followup_is_multilingual(user, monkeypatch):
    monkeypatch.setattr(i18n, "get_lang", lambda: "ta")
    r = agent.run_agent(user["id"], "I have a headache", [])
    assert i18n.STRINGS["q_duration"]["ta"] in r["content"]


def test_safety_check_runs_before_everything(user):
    r = agent.run_agent(user["id"], "I want to end my life", [])
    assert r["is_emergency"] and r["tools_used"] == ["safety_check"]


def test_i18n_complete_for_all_three_languages():
    for key, entry in i18n.STRINGS.items():
        assert set(entry) == {"en", "ta", "hi"} and all(entry.values()), key


# ---------- Vision / voice / SDK plumbing ----------
def test_vision_json_parsed_and_out_of_range_recomputed():
    raw = '```json\n{"fields":[{"test":"Hemoglobin","value":"10.5","unit":"g/dL","reference_range":"12-15.5","out_of_range":false},{"test":"","value":"1"}]}\n```'
    fields = labs.normalize_vision_fields(labs.parse_json_loose(raw)["fields"])
    assert len(fields) == 1 and fields[0]["out_of_range"] is True  # model's 'false' is NOT trusted


def test_gemini_calls_report_missing_key_honestly():
    assert llm.gemini_generate("hi")["ok"] is False
    assert llm.gemini_transcribe(b"x")["ok"] is False
    assert llm.gemini_embed(["a"]) is None


class FakeModels:
    def __init__(self):
        self.calls = []

    def generate_content(self, model, contents, config):
        self.calls.append(model)
        if model == "retired-model":
            raise RuntimeError("404 model not found")
        return types.SimpleNamespace(text=f"ok from {model}")

    def embed_content(self, model, contents, config):
        items = contents if isinstance(contents, list) else [contents]
        return types.SimpleNamespace(embeddings=[types.SimpleNamespace(values=[0.1, 0.2]) for _ in items])


def test_real_genai_types_with_fake_client_and_model_fallback(monkeypatch):
    fake = types.SimpleNamespace(models=FakeModels())
    monkeypatch.setenv("GOOGLE_API_KEY", "k")
    monkeypatch.setenv("GEMINI_MODEL", "retired-model")
    monkeypatch.setattr(llm, "_client", lambda key: fake)
    res = llm.gemini_generate("hello", language="Tamil")            # builds a real GenerateContentConfig
    assert res["ok"] and "gemini-2.5-flash" in res["text"] and fake.models.calls[0] == "retired-model"
    vis = llm.gemini_vision([(b"\x89PNG", "image/png")], "describe")  # builds a real types.Part
    assert vis["ok"]
    tr = llm.gemini_transcribe(b"RIFF", "audio/wav")
    assert tr["ok"]
    js = llm.gemini_generate_json("extract", parts=[(b"img", "image/png")])
    assert js["ok"]
    assert len(llm.gemini_embed(["a", "b", "c"])) == 3
