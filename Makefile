# FinSight AI — developer commands (macOS / Linux). Windows: see README for the equivalent commands.
PY := backend/.venv/bin/python

.PHONY: help setup backend-setup frontend-setup ai-setup ollama seed dev backend frontend test lint build docker-up clean
OLLAMA_MODEL ?= qwen2.5:3b

help:
	@echo "make setup     install backend (venv) + frontend dependencies"
	@echo "make ai-setup  install Ollama + local AI models (chat: $(OLLAMA_MODEL), embeddings: nomic-embed-text)"
	@echo "make seed      create the demo account  demo@finsight.ai / FinSight2026!"
	@echo "make dev       run backend (:8000) and frontend (:3000) together"
	@echo "make test      run the backend test suite"
	@echo "make lint      lint + type-check the frontend"
	@echo "make build     production build of the frontend"
	@echo "make docker-up run the full stack with Docker Compose (PostgreSQL + Redis)"

setup: backend-setup frontend-setup

backend-setup:
	python3 -m venv backend/.venv
	$(PY) -m pip install --upgrade pip
	$(PY) -m pip install -r backend/requirements-dev.txt

frontend-setup:
	cd frontend && npm install
	@test -f frontend/.env.local || cp frontend/.env.local.example frontend/.env.local

ai-setup:
	@command -v ollama >/dev/null || brew install ollama
	@$(MAKE) --no-print-directory ollama
	ollama pull $(OLLAMA_MODEL)
	ollama pull nomic-embed-text

# Start the Ollama server in the background if it is installed but not running
ollama:
	@if command -v ollama >/dev/null && ! curl -s -o /dev/null http://localhost:11434/api/tags; then \
		echo "Starting Ollama (local AI)…"; OLLAMA_CONTEXT_LENGTH=8192 nohup ollama serve >/tmp/finsight-ollama.log 2>&1 & sleep 2; \
	fi

seed:
	$(PY) backend/scripts/seed_db.py

backend:
	cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000

frontend:
	cd frontend && npm run dev

dev: ollama
	@echo "Backend → http://localhost:8000/docs   Frontend → http://localhost:3000"
	@trap 'kill 0' INT TERM; \
	(cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000) & \
	(cd frontend && npm run dev) & \
	wait

test:
	cd backend && .venv/bin/python -m pytest -q

lint:
	cd frontend && npm run lint && npm run typecheck

build:
	cd frontend && npm run build

docker-up:
	docker compose up --build

clean:
	rm -rf frontend/.next backend/.pytest_cache
	find backend -name __pycache__ -type d -prune -exec rm -rf {} +
