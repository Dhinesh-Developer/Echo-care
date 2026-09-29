# EchoCare — AI Healthcare Companion (Streamlit, V2–V4)

One Streamlit app: 21 pages across tracking, explainable AI, and care coordination — in a clean
light SaaS theme (blue primary, rounded cards, spacious dashboard layout). Only **two external
APIs are used anywhere**: Google Gemini and Tavily. Everything else (database, retrieval,
classifier, PDF, calendar, QR code) runs locally with no other account to set up.

## What's new since V1 (Streamlit MVP)

**V2 — Smarter AI**
- Gemini embeddings power semantic retrieval (`rag.py`); falls back to TF-IDF automatically if
  Gemini isn't configured, and every insight records which method produced it.
- Gemini Vision reads lab reports and prescriptions from a photo/PDF (`pages/6_📄_Medical_Reports.py`)
  and describes a symptom photo in neutral, non-diagnostic terms — never naming a condition.
- Voice symptom input via `st.audio_input` + Gemini transcription (English/Tamil/Hindi).
- Full UI + agent replies in English, Tamil or Hindi (`i18n.py`).
- Echo (the agent, `agent.py`) asks for duration/severity/trigger before answering a vague
  symptom report, but never loops twice on the same message.
- Every AI Insight has a "Why am I seeing this?" panel: retrieval method, the four confidence
  components with their weights, and the exact evidence chunks used.

**V3 — Clinical intelligence**
- Lab Trends: every test tracked across reports, out-of-range alerts with trend direction.
- Medicine Tracker: schedule, daily checklist, adherence %, Tavily-grounded interaction check.
- Health Timeline: when each symptom area started/changed, plotted across all source types.
- Risk flags (`health_rules.py`) combine tracker + vitals + labs + medicines + story into
  cross-source discussion points — always worded as "worth discussing," never a diagnosis.
- Diagnostic Guard gained a side-by-side opinion comparison with word-level diff highlighting
  and a conflict-signal heuristic (shared terms + negation mismatch).
- Vitals page: BMI/BP/sugar against standard target ranges, with trend charts.

**V4 — Care coordination**
- Admin can import a **real** doctor directory (CSV/Excel) that replaces the demo data
  app-wide; validates columns, normalises specialty names, and reports skipped rows.
- Appointments: booking, month calendar view, day-before/same-day reminders, `.ics` download.
- Family Profiles: manage a parent/child under one login; every module is per-profile.
- Emergency Card: public QR-linked page (no login) with blood group, allergies, contacts —
  owner-controlled, can be turned off or re-linked at any time.
- One-click PDF consultation report (`report_pdf.py`) with a section picker.
- Admin Dashboard: usage stats, feedback, doctor-directory import — no health data shown.

## Why some engineering choices look unusual (all verified, not guessed)

- **No tile-based map.** We tested `streamlit-folium` (broke against `streamlit==1.40.1`'s
  custom-component protocol — the child iframe never even loaded, confirmed in a real headless
  browser), `st.map` (needs a live fetch to Streamlit's Mapbox proxy, fails on restricted
  networks), and Plotly's `scatter_map` (blank canvas in our test browser). All three depend on
  an external tile/token service at runtime. Find Doctors instead uses a plain Plotly scatter
  plot of doctors' coordinates (color-coded by specialty) — needs zero network calls and is
  guaranteed to render anywhere. Real turn-by-turn navigation still works via the **Navigate**
  button, a plain `google.com/maps/dir` link that needs no API key.
- **TF-IDF fallback, not a hard Gemini dependency.** So the whole RAG pipeline still works with
  no key configured; it just retrieves by keyword instead of meaning.
- **SQLite, not Postgres/Mongo.** Zero services to provision. Ephemeral on Streamlit Community
  Cloud (resets on redeploy) — fine for coursework/demo; swap `db.py`'s `get_conn()` for a
  hosted Postgres connection for a persistent deployment.

## Verification performed (not just "should work")

- Every one of the 21 pages executed via Streamlit's `AppTest` framework with seeded data (not
  just import-checked) — 62 automated tests, all passing, including cross-page flows: family
  profile data isolation with cascading delete, emergency-card public/private access control,
  admin gating (first account, or `ADMIN_EMAILS` override), CSV directory import validation,
  appointment booking → calendar → `.ics` export, and the full follow-up-question conversation
  flow in the agent.
- Confirmed in a **real headless browser** (Playwright): sign-up, the light theme rendering,
  the animated banner, grouped sidebar navigation (`st.page_link` across all 21 pages), Vitals
  charts and status badges, the Echo follow-up flow, and the Find Doctors schematic map.
- A from-scratch clean virtualenv install from `requirements.txt` alone, then the full test
  suite re-run inside it — catches "works on my machine" dependency gaps.
- Two real bugs were found and fixed this way: the folium map issue above, and `st.page_link`
  raising inside Streamlit's `AppTest` harness (a testing-context-only limitation — real
  `streamlit run Home.py` resolves these correctly; the sidebar now falls back to a plain label
  if a link ever can't resolve, so no context can crash a page).

## Quick start

```bash
pip install -r requirements.txt
# System dependency for OCR fallback on scanned files (optional if you only use Gemini Vision):
sudo apt-get install tesseract-ocr

cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# edit in GOOGLE_API_KEY and TAVILY_API_KEY (both optional — the app degrades honestly without them)

streamlit run Home.py
```
First run trains the department classifier automatically if `ml/department_model.joblib` is
missing (or run `python ml/train_department_classifier.py` yourself — see its metrics report
in `ml/metrics.md`, ~92% test accuracy on a dataset generated directly from `specialties.py`).

To become an admin locally, either register the **first** account on a fresh database, or add
`ADMIN_EMAILS = "you@example.com"` to secrets.

## Deploy to Streamlit Community Cloud
1. Push this folder to GitHub.
2. New app on [share.streamlit.io](https://share.streamlit.io) → entrypoint `Home.py`.
3. Settings → Secrets:
   ```toml
   GOOGLE_API_KEY = "..."
   TAVILY_API_KEY = "..."
   ADMIN_EMAILS = "you@example.com"
   ```
4. `packages.txt` (tesseract-ocr, libgl1) is picked up automatically for OCR.

## Automated tests
```bash
pip install -r requirements-dev.txt
pytest tests/ -v
```
62 tests across `test_pages.py` (every page, real render), `test_v2_ai.py` (embeddings fallback,
follow-ups, i18n completeness, real `google-genai` types against a fake client), `test_v3_clinical.py`
(lab parsing, BMI/BP/sugar rules, risk flags, opinion comparison) and `test_v4_care.py` (directory
import, appointments/calendar/ICS, PDF, family isolation, emergency card, admin gating).

## Project structure
```
Home.py                      Landing/login/signup + animated hero + feature grid
specialties.py                SPECIALTIES dict — single source of truth for tagging, the
                              classifier, and the doctor-finder specialty filter
db.py                         SQLite persistence — every table for V1–V4
auth.py                       bcrypt auth + family "active profile" switching + admin check
config.py                     Reads keys from env or Streamlit secrets (secrets-safe: never
                              triggers Streamlit's "No secrets found" box when none exist)
llm.py                        The only two external APIs: Gemini (text/vision/voice/embeddings)
                              and Tavily — every call returns an honest ok/not-configured result
rag.py                        LE-RAG: chunking, semantic-or-TF-IDF retrieval, confidence scoring
agent.py                      Echo's tool orchestrator: safety → follow-up → RAG → web → Gemini
labs.py / health_rules.py     Lab parsing + trends; BMI/BP/sugar rules; cross-source risk flags
compare.py                    Opinion diff highlighting + conflict-signal heuristic
doctors_data.py                Demo directory (117 doctors) + CSV/Excel import + navigation links
department_classifier.py      Loads the trained specialty classifier (ml/)
docreader.py                  PDF→images for Vision; PyMuPDF/OCR text fallback
report_pdf.py                 One-click consultation PDF (reportlab)
calendar_utils.py             Month-grid HTML + .ics export for Appointments
banner.py / styles.py / ui.py Light-theme design system, animated banner, shared page scaffolding
i18n.py                       English/Tamil/Hindi strings for UI and the agent's follow-ups
ml/train_department_classifier.py   Trains directly on specialties.SPECIALTIES
pages/                        21 pages, grouped in the sidebar: Track / Understand / Care / Account
tests/                        62 AppTest + unit tests (see above)
```

## Known limitations (flagged, not hidden)
- Doctor directory is demo/seed data until an admin imports a real one (Admin → Doctor directory).
- SQLite resets on Streamlit Community Cloud redeploys — use a hosted DB for persistent production use.
- Department classifier is trained on generated examples from `specialties.py`, not hand-labeled
  patient data — solid for coursework, not a clinical-grade evaluation (see `ml/metrics.md`).
- PDF export supports English text reliably; Tamil/Hindi entries may not render in the PDF font.
