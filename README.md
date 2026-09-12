# Scheme Sarathi

AI-powered eligibility matching across **3,397 central and state government schemes** for Indian citizens. Answer a few questions in plain English, Hindi, or Hinglish — get back a personalised list of schemes you qualify for.

## Live Demo

| | URL |
|---|---|
| **App** | https://scheme-sarathi.vercel.app |
| **API** | https://scheme-sarathi-backend.onrender.com |
| **API Docs** | https://scheme-sarathi-backend.onrender.com/docs |

> The backend is on Render's free tier — the first request after 15 min of inactivity may take ~30 s to wake up.

---

## Features

- **Multilingual AI interview** — English, Hindi, Hinglish via voice or text
- **3,397 schemes** — central + state, across education, agriculture, health, housing, and more
- **Deterministic rule engine** — LLM extracts fields, Python decides eligibility (no hallucinations)
- **Eligible / Near-miss / Need-info** — three-tier result with per-condition breakdown
- **Document verification** — OCR (Tesseract) + Sarvam AI reads Aadhaar, PAN, income certificates, etc.
- **Voice input/output** — speech-to-text and text-to-speech via Sarvam AI
- **Assisted mode** — for CSC/NGO field workers to interview citizens and track follow-ups
- **Scheme detail pages** — eligibility conditions, how to apply, required documents

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 14, TypeScript, Tailwind CSS |
| Backend | FastAPI, Python 3.11 |
| AI / LLM | Sarvam AI — `sarvam-105b` (chat + document verification) |
| Speech | Sarvam AI — `saaras:v3` (STT), `bulbul:v3` (TTS) |
| OCR | Tesseract 5 + pytesseract (document text extraction) |
| Database | Supabase (PostgreSQL) |
| Eligibility | Pure Python rule engine (deterministic) |
| Frontend hosting | Vercel |
| Backend hosting | Render (Docker) |

---

## Local Development

### Prerequisites

| Tool | Minimum | Check |
|---|---|---|
| Python | 3.10+ | `python3 --version` |
| Node.js | 18+ | `node --version` |
| Tesseract OCR | 4+ | `tesseract --version` |

Install Tesseract on macOS:
```bash
brew install tesseract tesseract-lang
```

### One-click start

```bash
git clone https://github.com/jainsanskar0803/Scheme_Sarathi.git
cd Scheme_Sarathi
cp .env.example .env        # fill in your keys
./start.sh
```

Open **http://localhost:3000**

### Environment variables

```env
SARVAM_API_KEY=sk_...            # dashboard.sarvam.ai
SUPABASE_URL=https://...         # Supabase → Project Settings → API
SUPABASE_SERVICE_KEY=eyJ...      # Supabase → Project Settings → API → service_role key
USE_SUPABASE=true                # false = use local 14-scheme JSON fallback
```

### Manual start (two terminals)

**Terminal 1 — Backend:**
```bash
pip3 install -r backend/requirements.txt
python3 -m uvicorn backend.main:app --port 8000 --reload
```

**Terminal 2 — Frontend:**
```bash
cd frontend
cp .env.example .env.local       # set NEXT_PUBLIC_API_URL=http://localhost:8000
npm install
npm run dev
```

---

## Project Structure

```
Scheme_Sarathi/
├── start.sh                        ← one-click local start
├── .env.example                    ← environment variable template
├── Dockerfile                      ← backend Docker image (used by Render)
├── render.yaml                     ← Render deployment config
├── railway.json                    ← Railway deployment config (alternative)
│
├── backend/
│   ├── main.py                     ← FastAPI app entry point
│   ├── routes/
│   │   ├── profile.py              ← POST/GET/PATCH /api/profile
│   │   ├── chat.py                 ← POST /api/chat (Sarvam LLM)
│   │   ├── match.py                ← POST /api/match (rule engine)
│   │   ├── documents.py            ← POST /api/documents/verify (OCR + Sarvam)
│   │   ├── voice.py                ← POST /api/voice/transcribe + /speak
│   │   └── assisted.py             ← /api/assisted/* (field worker mode)
│   ├── services/
│   │   ├── extractor.py            ← Sarvam AI field extraction
│   │   ├── interviewer.py          ← question sequencing
│   │   ├── rule_engine.py          ← deterministic eligibility checks
│   │   ├── scheme_store.py         ← loads from Supabase or local JSON
│   │   ├── eligibility_extractor.py
│   │   └── formatter.py
│   ├── models/
│   │   ├── citizen_profile.py
│   │   ├── scheme.py
│   │   ├── match_result.py
│   │   ├── match_response.py
│   │   └── profile_session.py
│   ├── db/
│   │   ├── supabase.py             ← Supabase client
│   │   ├── session_store.py        ← interview session storage
│   │   └── assisted_store.py       ← citizen + follow-up storage
│   └── migrations/
│       └── assisted.sql            ← Supabase schema for assisted mode
│
├── frontend/
│   ├── app/
│   │   ├── page.tsx                ← Landing page
│   │   ├── interview/              ← AI chat interview (voice + text)
│   │   ├── results/                ← Scheme results (eligible/near-miss/need-info)
│   │   ├── scheme/[id]/            ← Individual scheme detail page
│   │   ├── documents/              ← Document verification
│   │   └── assisted/               ← Field worker mode
│   │       ├── page.tsx            ← Worker login
│   │       ├── citizens/           ← Citizen list
│   │       ├── new/                ← Register new citizen
│   │       ├── interview/          ← Redirect to interview with assisted context
│   │       └── results/            ← Results + follow-up tracking
│   └── lib/
│       ├── api.ts                  ← Typed fetch wrappers for all endpoints
│       └── types.ts                ← TypeScript types matching backend models
│
├── data/
│   └── seed_schemes.json           ← 14 curated schemes (local fallback, no DB needed)
│
├── scripts/
│   ├── ingest_all.py               ← Import all 3,397 Kaggle schemes into Supabase
│   ├── ingest.py
│   ├── seed_schemes.py
│   └── seed_supabase.py
│
├── sql/
│   ├── schema.sql
│   └── migrations/
│       ├── 001_interview_sessions.sql
│       └── 002_seed_schemes.sql
│
└── tests/                          ← pytest suite (unit + integration)
    ├── test_profile_api.py
    ├── test_chat_api.py
    ├── test_match_api.py
    ├── test_rule_engine.py
    ├── test_documents.py
    ├── test_voice.py
    ├── test_assisted.py
    └── test_supabase_integration.py
```

---

## API Reference

| Endpoint | Method | Description |
|---|---|---|
| `/health` | GET | Health check |
| `/api/profile` | POST | Create interview session |
| `/api/profile/{id}` | GET | Get profile + completeness score |
| `/api/profile/{id}` | PATCH | Update profile fields |
| `/api/chat` | POST | Send message, get next question (Sarvam LLM) |
| `/api/match` | POST | Run eligibility check across 3,397 schemes |
| `/api/documents/verify` | POST | Verify document via OCR + Sarvam AI |
| `/api/voice/transcribe` | POST | Speech → text (Sarvam saaras:v3) |
| `/api/voice/speak` | POST | Text → speech (Sarvam bulbul:v3) |
| `/api/assisted/citizens` | POST/GET | Create / list citizens (field worker) |
| `/api/assisted/citizens/{id}/followup` | GET/PUT | Track scheme follow-up status |

Full interactive docs: **https://scheme-sarathi-backend.onrender.com/docs**

---

## How It Works

```
User speaks or types (English / Hindi / Hinglish)
          ↓
Sarvam saaras:v3 transcribes audio (if voice)
          ↓
Sarvam sarvam-105b extracts structured fields
(age, income, caste, state, occupation, gender …)
          ↓
Rule engine checks each of 3,397 schemes
(pure Python — deterministic, no LLM)
          ↓
Returns: Eligible / Near-miss / Need-info / Ineligible
with per-condition PASS / FAIL / NEAR_MISS / NOT_PROVIDED
          ↓
Sarvam bulbul:v3 reads out the result (if voice mode)
```

**LLM only extracts. Code decides eligibility.**

---

## Deployment

### Frontend — Vercel

The frontend auto-deploys on every push to `main`.

Vercel project settings:
- **Framework:** Next.js
- **Root Directory:** `frontend`
- **Build command:** `npm run build`

Required env var in Vercel:
```
NEXT_PUBLIC_API_URL=https://scheme-sarathi-backend.onrender.com
```

### Backend — Render

The backend is deployed as a Docker container. `render.yaml` at the repo root configures everything.

To deploy your own instance:
1. Create account at render.com
2. New → Blueprint → connect this repo
3. Set env vars: `SARVAM_API_KEY`, `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`
4. Click Apply

---

## Supabase Setup (first time)

Run the SQL migrations in order from `sql/migrations/`, then seed the full dataset:

```bash
python3 -m scripts.ingest_all
```

Imports all 3,397 schemes into Supabase. Takes ~2-3 min. Safe to re-run (idempotent).

---

## Running Tests

```bash
# All unit tests (no Supabase needed)
pytest tests/ -v

# Integration tests (requires live Supabase credentials)
USE_SUPABASE=true pytest tests/test_supabase_integration.py -v
```

---

## Troubleshooting

**Port already in use**
```bash
lsof -ti:8000 | xargs kill
lsof -ti:3000 | xargs kill
./start.sh
```

**Only 14 schemes showing**
Run the ingestion script to populate Supabase with all 3,397 schemes:
```bash
python3 -m scripts.ingest_all
```

**Document verification fails**
Make sure Tesseract is installed: `brew install tesseract tesseract-lang` (macOS)

**Voice transcription fails**
Check `SARVAM_API_KEY` is set. Chrome sends `audio/webm;codecs=opus` — the backend strips the codec suffix automatically.

**Backend cold start on Render (free tier)**
First request after 15 min inactivity takes ~30 s. Upgrade to Render's paid plan ($7/month) for always-on.
