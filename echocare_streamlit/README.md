# EchoCare — AI Healthcare Companion (Streamlit Edition)

A single-deployable Streamlit app: longitudinal health tracking, an LE-RAG
insight engine, a tool-using AI agent, and a district-wise doctor finder —
styled in a takeUforward.org-inspired dark navy / orange theme.

**Only two external APIs are used, anywhere in this app: Google Gemini and
Tavily.** No Maps API, no paid tile provider, no vector DB service, no
MongoDB/Postgres — everything else runs locally (SQLite + scikit-learn TF-IDF
+ OpenStreetMap's free tiles), so it deploys cleanly on Streamlit Community
Cloud's free tier with zero other accounts to set up.

## Live architecture, mapped to the algorithms diagram

| Alg. | What it is | Where |
|---|---|---|
| 1 | Symptom/timeline extraction (NLP) | `rag.tag_themes()` / `rag.extract_timeline()` — keyword-spotting against `specialties.SPECIALTIES` + a timeline regex |
| 2 | OCR / doc parsing | `pages/5_📄_Medical_Reports.py` — PyMuPDF for digital PDFs, `pytesseract` OCR fallback for scans |
| 3 | LE-RAG orchestrator | `rag.py` — TF-IDF retrieval (not a neural embedding model — see note below), evidence-sufficiency gate, composite confidence score |
| 4 | Safety/emergency guard | `safety.py` — runs before every story entry and chat message reaches the LLM |
| 5 | Department recommendation | `ml/train_department_classifier.py` + `department_classifier.py` — TF-IDF+LogReg trained **directly on `specialties.SPECIALTIES`** |
| 6 | Facility/doctor ranking | `doctors_data.py` — composite score (rating + experience + proximity) |

## Why TF-IDF instead of a neural embedding model

Streamlit Community Cloud's free tier caps out around 1GB RAM. A
transformer embedding model (`sentence-transformers`, even a "small" one)
pulls in `torch` and regularly OOMs that tier on deploy. TF-IDF
(`scikit-learn`) is zero-download, sub-millisecond, and works well for the
short symptom/health-log text this app deals with. If you deploy somewhere
with more headroom, swap `_fit_and_search()` in `rag.py` for a real embedding
model — the rest of the LE-RAG pipeline (chunking, evidence-sufficiency gate,
confidence scoring) doesn't need to change.

## Why SQLite instead of MongoDB/Postgres

Matches the "deploy through Streamlit only" requirement — no external
database service to provision. **Caveat:** Streamlit Community Cloud's
filesystem is ephemeral and resets on redeploy/sleep. Fine for a class demo
or local run; for a persistent production deployment, point `db.py`'s
`get_conn()` at a hosted Postgres/Supabase connection instead — it's the only
file that would need to change.

## Quick start (local)

```bash
pip install -r requirements.txt
# System dependency for OCR (Debian/Ubuntu):
sudo apt-get install tesseract-ocr

cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# edit in your GOOGLE_API_KEY and TAVILY_API_KEY

streamlit run app.py
```

## Deploy to Streamlit Community Cloud

1. Push this folder to a GitHub repo.
2. On [share.streamlit.io](https://share.streamlit.io), point a new app at
   `app.py` in that repo.
3. In the app's **Settings → Secrets**, paste:
   ```toml
   GOOGLE_API_KEY = "..."
   TAVILY_API_KEY = "..."
   ```
4. `packages.txt` (tesseract-ocr, libgl1) is picked up automatically for the
   OCR system dependency — nothing else to configure.

## Automated tests

```bash
pip install -r requirements-dev.txt
pytest tests/ -v
```
19 tests, using Streamlit's own `AppTest` framework — these actually execute
every page's script (not just import it) and assert on real behavior: the
emergency guard blocking storage, symptom auto-tagging, the tracker streak,
and the evidence-sufficiency gate refusing to generate an insight until
there's real corroborating data.

Running this suite while building caught a real bug before deployment: the
map's default dark tile provider (CartoDB) silently started requiring an API
key we don't have — switched to keyless OpenStreetMap tiles instead. This is
exactly the kind of break AppTest catches that a manual click-through often
misses.

## Project structure
```
app.py                      Home page: login/signup + animated hero + feature grid
specialties.py               The project's SPECIALTIES dict — single source of truth
db.py                        SQLite persistence (all 10+ tables)
auth.py                      bcrypt password auth via session_state
rag.py                       LE-RAG: chunking, TF-IDF retrieval, confidence scoring
agent.py                     Tool-using orchestrator (safety → RAG → web search → Gemini)
llm.py                       The only two external API wrappers: Gemini + Tavily
doctors_data.py              District-wise seed doctor directory (117 doctors, 10 districts)
department_classifier.py     Loads the trained specialty classifier
banner.py                    PIL-generated animated slideshow (offline, no image APIs)
styles.py                    takeUforward-style dark/orange CSS design system
safety.py                    Emergency-language guard
ml/train_department_classifier.py   Trains on specialties.SPECIALTIES directly
pages/                       One file per module (Streamlit auto-multipage)
tests/test_app.py            AppTest-based regression suite (19 tests)
```

## Known limitations (flagged, not hidden)
- **Doctor directory is demo/seed data** (117 doctors, 10 Tamil Nadu districts,
  procedurally generated) — clearly labeled `is_demo_data: true` everywhere
  it's shown. Swap `doctors_data.DOCTORS` for a real hospital dataset or a
  Google Places integration for production use.
- **SQLite is ephemeral on Streamlit Community Cloud** — see note above.
- **Department classifier is trained on generated examples** from the
  `SPECIALTIES` keyword map (246 examples, 92% test accuracy — see
  `ml/metrics.md`), not hand-labeled patient data. Solid for demo/coursework;
  augment with a curated dataset for a clinical-grade evaluation.
- **Map tiles are OpenStreetMap** (not a dark-themed provider) since every
  dark tile provider we found now requires its own API key — this keeps the
  project to exactly two external services as required.
