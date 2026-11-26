# FinSight AI — backend image (FastAPI + ML stack, CPU only)
# Runs on Hugging Face Spaces (port 7860, user 1000), Docker Compose (PORT=8000) or any container host.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PORT=7860
WORKDIR /app

# libgomp1: OpenMP runtime needed by XGBoost and scikit-learn
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements-postgres.txt ./
# CPU-only PyTorch keeps the image ~2 GB smaller than the default CUDA build
RUN pip install --index-url https://download.pytorch.org/whl/cpu torch \
    && pip install -r requirements.txt -r requirements-postgres.txt

COPY . .
RUN useradd --create-home --uid 1000 finsight \
    && mkdir -p data/models data/reports \
    && chown -R finsight:finsight /app
USER finsight

EXPOSE 7860
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s CMD curl -fs "http://localhost:${PORT}/health" || exit 1
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
