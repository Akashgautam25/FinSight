"""
FinSight AI — Demo Data Seeder (command-line entry point)

    backend/.venv/bin/python backend/scripts/seed_db.py      (or: make seed)
    docker compose exec backend python scripts/seed_db.py   (Docker)

Creates the demo account demo@finsight.ai / FinSight2026! — see app/seed.py.
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.seed import seed  # noqa: E402

if __name__ == "__main__":
    print("✓", asyncio.run(seed()))
