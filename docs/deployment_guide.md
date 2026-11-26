# FinSight AI — Deployment Guide

## 1. Local development (recommended for demos)
Prerequisites: Python 3.11+, Node 18+, macOS: `brew install libomp`.
```bash
make setup && make seed && make dev
```
Frontend http://localhost:3000 · API http://localhost:8000/docs · demo login `demo@finsight.ai` / `FinSight2026!`.
Data lives in `backend/data/` (SQLite DB, development secret key, trained models, PDFs) — delete the folder to reset.

**Offline presentation:** set `MARKET_DATA_MODE=demo` in `.env` to use simulated data only (no network needed).

## 2. Docker Compose (PostgreSQL + Redis)
```bash
cp .env.example .env          # set SECRET_KEY, optional API keys
docker compose up --build
docker compose exec backend python scripts/seed_db.py
```
Services: `postgres` (5432, internal), `redis` (internal), `backend` (8000), `frontend` (3000). Volumes persist the
database, cache and `backend/data`. The frontend image bakes `NEXT_PUBLIC_API_URL` at build time (build arg).

## 3. Cloud deployment (free): Render + Vercel

* **Backend → Render free plan** (512 MB RAM) using the *lite* build `backend/requirements-cloud.txt`: the full app
  without PyTorch, so the LSTM and FinBERT are disabled online (`ENABLE_TORCH=false`; Linear Regression, Random
  Forest and XGBoost forecasts and the finance-lexicon sentiment model still work). Measured peak memory ≈ 170 MB.
* **Frontend → Vercel** (free).
* **AI → Groq** free API key (`openai/gpt-oss-120b`; the backend falls back to another available Groq model automatically).

### Backend → Render
1. Create a free account at render.com (sign up with GitHub) → *Account settings → API keys* → create a key.
2. Create a free Groq key at console.groq.com/keys.
3. From the project root:
   ```bash
   RENDER_API_KEY=rnd_xxx GROQ_API_KEY=gsk_xxx backend/.venv/bin/python deploy/deploy_backend_render.py
   ```
   (Alternatively: Render dashboard → *New → Blueprint* → this repository, which uses `render.yaml`, then set `GROQ_API_KEY`.)

Online behaviour: `ENVIRONMENT=production`; the SQLite database resets whenever the free instance restarts and the
demo account is recreated automatically (`SEED_DEMO_ON_STARTUP=true`). Free instances sleep after 15 minutes
without traffic; the first request after that takes ~1 minute while the backend wakes up.

### Full-feature alternative: Hugging Face Spaces (PRO)
Docker Spaces need a Hugging Face PRO subscription. With one, `HF_TOKEN=… GROQ_API_KEY=… backend/.venv/bin/python
deploy/deploy_backend_hf.py` deploys the full image (LSTM + FinBERT, 16 GB RAM) from `backend/Dockerfile`.

### Frontend → Vercel
```bash
cd frontend
npx vercel login
npx vercel link --yes --project finsight-ai
npx vercel env add NEXT_PUBLIC_API_URL production   # value: your Render URL, e.g. https://finsight-api.onrender.com
npx vercel deploy --prod
```
The backend already allows `https://finsight-ai*.vercel.app` via `CORS_ORIGIN_REGEX`; if you use another project
name, re-run the backend deploy with `FRONTEND_PROJECT=<name>`.

### Other hosts
`backend/Dockerfile` reads `$PORT`, so it also runs on Render, Railway, Fly.io, Cloud Run or AWS App Runner
(give it at least 2 GB RAM). For persistent data set `DATABASE_URL=postgresql+asyncpg://…` (e.g. Neon) and
mount `/app/data` for trained models and PDFs.

## 4. Production checklist
- [ ] Strong `SECRET_KEY`, `ENVIRONMENT=production` (disables dev reset links)
- [ ] HTTPS in front of both services; restrictive `CORS_ORIGINS`
- [ ] PostgreSQL backups
- [ ] SMTP configured for password resets
- [ ] Note Yahoo Finance terms: `yfinance` is for personal/educational use; use a licensed data provider commercially
