# Scheme Sarathi

AI-powered eligibility matching across **3,397 central and state government schemes** for Indian citizens. Answer a few questions in plain English, Hindi, or Hinglish — get back a personalised list of schemes you qualify for.

---

## One-click start

```bash
./start.sh
```

That's it. The script:
1. Checks Python and Node are installed
2. Installs missing dependencies automatically
3. Starts the FastAPI backend on **port 8000**
4. Starts the Next.js frontend on **port 3000**
5. Opens both with `Ctrl+C` to stop

**Open your browser at → [http://localhost:3000](http://localhost:3000)**

---

## Prerequisites

| Tool | Minimum version | Check |
|------|----------------|-------|
| Python | 3.10+ | `python3 --version` |
| Node.js | 18+ | `node --version` |
| npm | 8+ | `npm --version` |

---

## First-time setup

### 1. Clone / download the project

```bash
git clone <repo-url>
cd Scheme_Sarathi
```

### 2. Create your `.env` file

```bash
cp .env.example .env
```

Open `.env` and fill in three values:

```env
SARVAM_API_KEY=sk_...          # from dashboard.sarvam.ai
SUPABASE_URL=https://...       # from Supabase project settings
SUPABASE_SERVICE_KEY=sb_...    # from Supabase project settings
USE_SUPABASE=true
```

### 3. Run

```bash
./start.sh
```

---

## Manual start (if you prefer two terminals)

**Terminal 1 — Backend:**
```bash
cd Scheme_Sarathi
pip3 install -r requirements.txt

SARVAM_API_KEY=sk_... \
SUPABASE_URL=https://... \
SUPABASE_SERVICE_KEY=sb_... \
USE_SUPABASE=true \
python3 -m uvicorn backend.main:app --port 8000 --reload
```

**Terminal 2 — Frontend:**
```bash
cd Scheme_Sarathi/frontend
npm install
npm run dev
```

---

## Project structure

```
Scheme_Sarathi/
├── start.sh                  ← one-click start (run this)
├── .env                      ← your secrets (not committed)
├── .env.example              ← template
├── requirements.txt          ← Python deps
│
├── backend/
│   ├── main.py               ← FastAPI app
│   ├── routes/
│   │   ├── profile.py        ← POST/GET/PATCH /api/profile
│   │   ├── chat.py           ← POST /api/chat  (Sarvam LLM)
│   │   └── match.py          ← POST /api/match (rule engine)
│   ├── services/
│   │   ├── extractor.py      ← Sarvam AI field extraction
│   │   ├── interviewer.py    ← question sequencing
│   │   ├── rule_engine.py    ← deterministic eligibility checks
│   │   └── scheme_store.py   ← loads schemes from Supabase or JSON
│   ├── models/
│   │   ├── citizen_profile.py
│   │   └── scheme.py
│   └── db/
│       └── supabase.py
│
├── frontend/
│   ├── app/
│   │   ├── page.tsx          ← Home / landing
│   │   ├── interview/        ← AI chat interview
│   │   ├── results/          ← scheme results (eligible / near-miss / need-info)
│   │   └── scheme/[id]/      ← individual scheme detail
│   └── lib/
│       ├── api.ts            ← fetch wrappers
│       └── types.ts          ← TypeScript types matching backend
│
├── data/
│   └── seed_schemes.json     ← 14 curated schemes (local fallback)
│
├── scripts/
│   └── ingest_all.py         ← import all 3,397 Kaggle schemes into Supabase
│
└── tests/                    ← pytest test suite
```

---

## Supabase setup (first time only)

If you are setting up a fresh Supabase project, run the SQL files in order:

```
sql/01_create_tables.sql     ← create interview_sessions + seed_schemes
sql/02_disable_rls.sql       ← disable RLS (uses service key, safe)
```

Then seed the full dataset:

```bash
python3 -m scripts.ingest_all
```

This imports all 3,397 schemes. Takes about 2-3 minutes. Safe to run multiple times (idempotent).

---

## API overview

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/profile` | POST | Create interview session |
| `/api/profile/{id}` | GET | Get profile + completeness |
| `/api/profile/{id}` | PATCH | Update profile fields |
| `/api/chat` | POST | Send a message, get next question |
| `/api/match` | POST | Run eligibility check across all 3,397 schemes |
| `/docs` | GET | Interactive Swagger UI |

---

## How it works

```
User types a message (English / Hindi / Hinglish)
        ↓
Sarvam AI (sarvam-105b) extracts structured fields
(age, income, caste, state, occupation, …)
        ↓
Rule engine checks each of 3,397 schemes
(pure Python, no LLM, deterministic)
        ↓
Returns: eligible / near-miss / need-info / ineligible
with per-condition PASS / FAIL / NEAR_MISS / NOT_PROVIDED
```

**LLM only extracts. Code decides eligibility.**

---

## Running tests

```bash
# Unit tests (no Supabase needed)
pytest tests/ -v

# Integration tests (requires USE_SUPABASE=true + valid credentials)
USE_SUPABASE=true pytest tests/test_supabase_integration.py -v
```

---

## Tech stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 14, TypeScript, Tailwind CSS |
| Backend | FastAPI, Python 3.12 |
| AI / LLM | Sarvam AI (`sarvam-105b`) |
| Database | Supabase (PostgreSQL) |
| Eligibility | Pure Python rule engine |
| Schemes | 3,397 from MyScheme / Kaggle dataset |

---

## Troubleshooting

**Port already in use**
```bash
lsof -ti:8000 | xargs kill  # kill backend
lsof -ti:3000 | xargs kill  # kill frontend
./start.sh
```

**"SARVAM_API_KEY is not set" error**
Make sure `.env` exists in the project root (not inside `frontend/` or `backend/`).

**Schemes not loading / only 14 schemes**
Run the ingestion script to populate Supabase:
```bash
python3 -m scripts.ingest_all
```

**Frontend white screen after restart**
The Next.js cache got stale. Fix:
```bash
rm -rf frontend/.next
./start.sh
```
