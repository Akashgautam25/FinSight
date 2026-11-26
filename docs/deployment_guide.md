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

## 3. Cloud deployment
* **Frontend → Vercel / Netlify:** root `frontend/`, env `NEXT_PUBLIC_API_URL=https://<your-api>`.
* **Backend → Render / Railway / Fly.io / AWS App Runner:** build from `backend/Dockerfile`. Set:
  * `ENVIRONMENT=production`, `SECRET_KEY=<64+ random chars>` (required in production)
  * `DATABASE_URL=postgresql+asyncpg://…` (Neon, Supabase, RDS…)
  * `REDIS_URL=redis://…` (Upstash, Elasticache) — optional
  * `CORS_ORIGINS=https://<your-frontend>` and `FRONTEND_URL=https://<your-frontend>`
  * optional: `GOOGLE_API_KEY`, `SMTP_*`
* Mount persistent storage at `/app/data` so trained models and PDFs survive restarts.
* Run a single backend instance (training jobs and the alert loop are in-process); scale out with a task queue later.

## 4. Production checklist
- [ ] Strong `SECRET_KEY`, `ENVIRONMENT=production` (disables dev reset links)
- [ ] HTTPS in front of both services; restrictive `CORS_ORIGINS`
- [ ] PostgreSQL backups
- [ ] SMTP configured for password resets
- [ ] Note Yahoo Finance terms: `yfinance` is for personal/educational use; use a licensed data provider commercially
