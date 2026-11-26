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

## 3. Cloud deployment (free): Hugging Face Spaces + Vercel

The backend needs ~2–3 GB RAM (PyTorch, FinBERT, XGBoost, LSTM), so it runs on a free **Hugging Face Docker
Space** (2 vCPU / 16 GB). The Next.js frontend runs on **Vercel**. The online AI uses a free **Groq** key
(local Ollama is not reachable from the internet).

### Backend → Hugging Face Space
1. Create a free account at huggingface.co → *Settings → Access Tokens* → new token with **Write** access.
2. Create a free Groq key at console.groq.com/keys.
3. From the project root:
   ```bash
   HF_TOKEN=hf_xxx GROQ_API_KEY=gsk_xxx backend/.venv/bin/python deploy/deploy_backend_hf.py
   ```
   The script creates `https://huggingface.co/spaces/<user>/finsight-api`, sets the configuration and secrets
   (`SECRET_KEY`, `GROQ_API_KEY`), uploads `backend/` and waits for the build (~5–10 min the first time).
   API URL: `https://<user>-finsight-api.hf.space` (docs at `/docs`).

Online behaviour: `ENVIRONMENT=production`, the SQLite database resets on every restart and the demo account is
recreated automatically (`SEED_DEMO_ON_STARTUP=true`); AAPL and NVDA models are trained in the background
(`PRETRAIN_SYMBOLS`). Free Spaces sleep after 48 h without traffic — open the API URL once to wake it (~1 min).

### Frontend → Vercel
```bash
cd frontend
npx vercel login
npx vercel link --yes --project finsight-ai
npx vercel env add NEXT_PUBLIC_API_URL production   # value: https://<user>-finsight-api.hf.space
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
