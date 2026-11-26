# FinSight AI — backend image (FastAPI + ML stack, CPU only)
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

# libgomp1: OpenMP runtime needed by XGBoost and scikit-learn
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements-postgres.txt ./
# CPU-only PyTorch keeps the image ~2 GB smaller than the default CUDA build
RUN pip install --index-url https://download.pytorch.org/whl/cpu torch \
    && pip install -r requirements.txt -r requirements-postgres.txt

COPY . .
RUN mkdir -p data/models data/reports && useradd --create-home finsight && chown -R finsight /app
USER finsight

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s CMD curl -fs http://localhost:8000/health || exit 1
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
