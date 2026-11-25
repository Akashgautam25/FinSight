# FinSight AI — Production Deployment Guide

## 1. Local Environment Setup

### Prerequisites
- Node.js v18.17+
- Python 3.11+
- PostgreSQL 16 (or Docker)
- Redis 7 (or Docker)

### Step 1: Environment Variables
Copy `.env.example` in the project root:
```bash
cp .env.example .env
```
Populate external API keys (Alpha Vantage, Finnhub, Google Gemini) or use demo mode.

### Step 2: Database Setup & Seeding
```bash
# Start Postgres & Redis locally or with Docker
docker run -d --name finsight_pg -p 5432:5432 -e POSTGRES_USER=finsight -e POSTGRES_PASSWORD=password -e POSTGRES_DB=finsight_db pgvector/pgvector:pg16
docker run -d --name finsight_redis -p 6379:6379 redis:7-alpine

# Run database seeder
cd infrastructure/scripts
python3 seed_db.py
```

### Step 3: Run Backend Service
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Step 4: Run Frontend Application
```bash
cd frontend
npm install
npm run dev
```
Open **http://localhost:3000** in your browser.

---

## 2. Docker Compose Deployment (Recommended)
Launch the entire multi-container stack with a single command:
```bash
docker-compose up --build
```
This automatically builds and orchestrates:
- `finsight_postgres` on port 5432
- `finsight_redis` on port 6379
- `finsight_backend` on port 8000
- `finsight_celery` background task worker
- `finsight_frontend` on port 3000

---

## 3. Production Cloud Deployment
- **Frontend**: Deploy `frontend/` directly to **Vercel** with environment variable `NEXT_PUBLIC_API_URL`.
- **Backend**: Deploy `backend/` as a Web Service on **Render** or **AWS ECS/App Runner** with managed PostgreSQL (Neon / Supabase) and managed Redis (Upstash).
