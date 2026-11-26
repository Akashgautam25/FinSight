"""
Deploy the FinSight AI backend to Render (free plan, "lite" build without PyTorch).

Usage (from the project root):
    RENDER_API_KEY=rnd_xxx GROQ_API_KEY=gsk_xxx backend/.venv/bin/python deploy/deploy_backend_render.py

Optional environment variables:
    SERVICE_NAME       Render service name (default: finsight-api)
    REPO_URL           Git repository (default: https://github.com/Akashgautam25/FinSight)
    FRONTEND_PROJECT   Vercel project allowed by CORS (default: finsight-ai)
    REGION             Render region (default: singapore)

Creates the web service on first run (with a random SECRET_KEY), otherwise updates its
environment and triggers a new deploy. Keys are stored as Render environment variables,
never in git. Same settings as render.yaml.
"""

import os
import re
import secrets
import sys
import time

import httpx

API = "https://api.render.com/v1"


def main() -> None:
    key = os.environ.get("RENDER_API_KEY")
    if not key:
        sys.exit("Set RENDER_API_KEY (Render dashboard → Account settings → API keys).")
    client = httpx.Client(base_url=API, headers={"Authorization": f"Bearer {key}", "Accept": "application/json"}, timeout=60)

    def call(method: str, path: str, **kw):
        r = client.request(method, path, **kw)
        if r.status_code >= 400:
            sys.exit(f"Render API {method} {path} failed: HTTP {r.status_code} {r.text[:500]}")
        return r.json() if r.content else None

    name = os.environ.get("SERVICE_NAME", "finsight-api")
    repo = os.environ.get("REPO_URL", "https://github.com/Akashgautam25/FinSight")
    frontend = os.environ.get("FRONTEND_PROJECT", "finsight-ai")

    owners = call("GET", "/owners", params={"limit": 20})
    owner_id = owners[0]["owner"]["id"]

    env = {
        "PYTHON_VERSION": "3.12.8",
        "ENVIRONMENT": "production",
        "ENABLE_TORCH": "false",
        "SENTIMENT_BACKEND": "lexicon",
        "SEED_DEMO_ON_STARTUP": "true",
        "LLM_PROVIDER": "auto",
        "GROQ_MODEL": os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b"),
        "CORS_ORIGIN_REGEX": rf"https://{re.escape(frontend)}[a-z0-9-]*\.vercel\.app",
    }
    for k in ("GROQ_API_KEY", "GOOGLE_API_KEY", "OPENAI_API_KEY"):
        if os.environ.get(k):
            env[k] = os.environ[k]

    existing = [s["service"] for s in call("GET", "/services", params={"name": name, "limit": 20})
                if s["service"]["name"] == name]
    if existing:
        service = existing[0]
        sid = service["id"]
        # Update variables one by one (keeps SECRET_KEY and anything set in the dashboard)
        for k, v in env.items():
            call("PUT", f"/services/{sid}/env-vars/{k}", json={"value": v})
        call("POST", f"/services/{sid}/deploys", json={"clearCache": "do_not_clear"})
        print(f"Updated {name}; new deploy triggered")
    else:
        env["SECRET_KEY"] = secrets.token_urlsafe(64)
        body = {
            "type": "web_service",
            "name": name,
            "ownerId": owner_id,
            "repo": repo,
            "branch": "main",
            "rootDir": "backend",
            "autoDeploy": "yes",
            "envVars": [{"key": k, "value": v} for k, v in env.items()],
            "serviceDetails": {
                "runtime": "python",
                "plan": "free",
                "region": os.environ.get("REGION", "singapore"),
                "healthCheckPath": "/health",
                "envSpecificDetails": {
                    "buildCommand": "pip install -r requirements-cloud.txt",
                    "startCommand": "uvicorn app.main:app --host 0.0.0.0 --port $PORT --proxy-headers --forwarded-allow-ips='*'",
                },
            },
        }
        created = call("POST", "/services", json=body)
        service = created.get("service", created)
        sid = service["id"]
        print(f"Created {name} ({sid})")

    url = (service.get("serviceDetails") or {}).get("url") or call("GET", f"/services/{sid}")["serviceDetails"]["url"]
    print(f"Building… (first build ~5 min)  {url}")
    started, status = time.time(), None
    while time.time() - started < 1500:
        deploys = call("GET", f"/services/{sid}/deploys", params={"limit": 1})
        status = deploys[0]["deploy"]["status"] if deploys else "pending"
        print(f"  [{int(time.time() - started):4d}s] {status}")
        if status in ("live", "build_failed", "update_failed", "canceled", "deactivated"):
            break
        time.sleep(20)
    print(f"\nService: https://dashboard.render.com/web/{sid}\nAPI:     {url}\nStatus:  {status}")
    if status != "live":
        sys.exit(1)


if __name__ == "__main__":
    main()
