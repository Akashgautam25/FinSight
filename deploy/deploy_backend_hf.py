"""
Deploy the FinSight AI backend to a Hugging Face Docker Space.

Usage (from the project root):
    HF_TOKEN=hf_xxx GROQ_API_KEY=gsk_xxx backend/.venv/bin/python deploy/deploy_backend_hf.py

Optional environment variables:
    SPACE_NAME          Space name (default: finsight-api)
    GOOGLE_API_KEY      Gemini key (used before Groq if set)
    FRONTEND_PROJECT    Vercel project name allowed by CORS (default: finsight-ai)
    ROTATE_SECRET=1     Generate a new JWT SECRET_KEY (signs everyone out)

Keys are stored as Space *secrets* (encrypted, never committed). Re-running the script
uploads the latest backend code and restarts the Space.
"""

import io
import os
import re
import secrets
import sys
import time
from pathlib import Path

from huggingface_hub import HfApi
from huggingface_hub.utils import RepositoryNotFoundError

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"

SPACE_README = """---
title: FinSight AI API
emoji: 📈
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
license: mit
short_description: FinSight AI backend — FastAPI, ML forecasts, LLM agent
---

# FinSight AI — backend API

FastAPI backend of [FinSight AI](https://github.com/Akashgautam25/FinSight): market data, portfolio
analytics, ML price forecasts, FinBERT sentiment and a tool-calling LLM research agent.

* Health: `/health` · Interactive API docs: `/docs`
* The database resets when the Space restarts; the demo account `demo@finsight.ai` is recreated automatically.
"""


def main() -> None:
    token = os.environ.get("HF_TOKEN")
    if not token:
        sys.exit("Set HF_TOKEN (a Hugging Face access token with write permission).")
    api = HfApi(token=token)
    user = api.whoami()["name"]
    space = os.environ.get("SPACE_NAME", "finsight-api")
    repo_id = f"{user}/{space}"
    frontend_project = os.environ.get("FRONTEND_PROJECT", "finsight-ai")

    try:
        api.repo_info(repo_id, repo_type="space")
        created = False
    except RepositoryNotFoundError:
        api.create_repo(repo_id, repo_type="space", space_sdk="docker", private=False)
        created = True
    print(f"{'Created' if created else 'Updating'} Space {repo_id}")

    variables = {
        "ENVIRONMENT": "production",
        "MARKET_DATA_MODE": "auto",
        "LLM_PROVIDER": "auto",
        "GROQ_MODEL": os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile"),
        "SENTIMENT_BACKEND": "auto",
        "SEED_DEMO_ON_STARTUP": "true",
        "PRETRAIN_SYMBOLS": "AAPL,NVDA",
        "CORS_ORIGIN_REGEX": rf"https://{re.escape(frontend_project)}[a-z0-9-]*\.vercel\.app",
        "ALERT_CHECK_INTERVAL_SECONDS": "300",
    }
    for key, value in variables.items():
        api.add_space_variable(repo_id, key, value)

    if created or os.environ.get("ROTATE_SECRET") == "1":
        api.add_space_secret(repo_id, "SECRET_KEY", secrets.token_urlsafe(64))
    for key in ("GROQ_API_KEY", "GOOGLE_API_KEY", "OPENAI_API_KEY"):
        if os.environ.get(key):
            api.add_space_secret(repo_id, key, os.environ[key])
            print(f"  secret {key} set")

    print("Uploading backend code…")
    api.upload_folder(
        folder_path=str(BACKEND),
        repo_id=repo_id,
        repo_type="space",
        ignore_patterns=[".venv/*", "data/*", "**/__pycache__/*", "*.pyc", ".pytest_cache/*", "tests/*", ".env", "*.db"],
        commit_message="Deploy FinSight AI backend",
    )
    api.upload_file(path_or_fileobj=io.BytesIO(SPACE_README.encode()), path_in_repo="README.md",
                    repo_id=repo_id, repo_type="space", commit_message="Space metadata")

    host = f"{user}-{space}".lower().replace("_", "-").replace(".", "-")
    url = f"https://{host}.hf.space"
    print(f"Building… (first build takes ~5-10 minutes)  {url}")
    stage, started = None, time.time()
    while time.time() - started < 1800:
        stage = api.get_space_runtime(repo_id).stage
        print(f"  [{int(time.time() - started):4d}s] {stage}")
        if stage in ("RUNNING", "BUILD_ERROR", "RUNTIME_ERROR", "CONFIG_ERROR"):
            break
        time.sleep(20)
    print(f"\nSpace: https://huggingface.co/spaces/{repo_id}\nAPI:   {url}\nStage: {stage}")
    if stage != "RUNNING":
        sys.exit(1)


if __name__ == "__main__":
    main()
