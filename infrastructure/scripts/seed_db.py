"""Compatibility wrapper — the seeder lives in backend/scripts/seed_db.py (so it ships in the Docker image)."""
import os
import runpy

runpy.run_path(os.path.join(os.path.dirname(__file__), "../../backend/scripts/seed_db.py"), run_name="__main__")
