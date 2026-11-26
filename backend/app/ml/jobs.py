"""
FinSight AI — Background Training Jobs

Training is CPU-bound and takes ~10–60 s, so it must never run on the event loop.
Jobs run as asyncio tasks that hand the pipeline to a worker thread; a semaphore
serialises training so concurrent requests cannot overload the machine. Progress
is kept in memory and polled by the UI via GET /predictions/{symbol}/status.

On completion the run is recorded in the database (ml_models + model_evaluations)
and the requesting user receives an in-app notification.
"""

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from app.database import AsyncSessionLocal
from app.ml.pipeline import TrainingPipeline

logger = logging.getLogger("finsight.ml.jobs")


class TrainingJobManager:
    def __init__(self, max_concurrent: int = 1):
        self._jobs: Dict[str, dict] = {}
        self._tasks: set = set()
        self._sem = asyncio.Semaphore(max_concurrent)

    def status(self, symbol: str) -> Optional[dict]:
        job = self._jobs.get(symbol.upper())
        return dict(job) if job else None

    def is_active(self, symbol: str) -> bool:
        job = self._jobs.get(symbol.upper())
        return bool(job and job["status"] in ("queued", "running"))

    def submit(self, symbol: str, model_types: List[str], lookback_years: int, user_id: Optional[str] = None) -> dict:
        symbol = symbol.upper()
        if self.is_active(symbol):
            return self.status(symbol)
        job = {
            "job_id": str(uuid.uuid4()),
            "symbol": symbol,
            "status": "queued",
            "progress": 0.0,
            "message": "Waiting for a free training slot",
            "model_types": model_types,
            "queued_at": datetime.now(timezone.utc).isoformat(),
            "started_at": None,
            "finished_at": None,
            "error": None,
        }
        self._jobs[symbol] = job
        task = asyncio.create_task(self._run(symbol, model_types, lookback_years, user_id))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return dict(job)

    async def _run(self, symbol: str, model_types: List[str], lookback_years: int, user_id: Optional[str]) -> None:
        job = self._jobs[symbol]

        def progress(p: float, message: str) -> None:  # called from the worker thread
            job["progress"] = round(min(max(p, 0.0), 1.0), 3)
            job["message"] = message

        async with self._sem:
            job.update(status="running", started_at=datetime.now(timezone.utc).isoformat(), message="Starting")
            try:
                pipeline = TrainingPipeline(symbol, model_types, lookback_years, progress=progress)
                metadata = await asyncio.to_thread(pipeline.run)
                job.update(status="completed", progress=1.0, message="Training complete")
                await self._persist(metadata, user_id)
            except Exception as exc:
                logger.exception("Training failed for %s", symbol)
                job.update(status="failed", error=str(exc), message="Training failed")
                await self._notify(user_id, "training_failed", f"Training failed for {symbol}", str(exc), {"symbol": symbol})
            finally:
                job["finished_at"] = datetime.now(timezone.utc).isoformat()

    async def _persist(self, metadata: dict, user_id: Optional[str]) -> None:
        from app.models import MLModel, ModelEvaluation

        symbol = metadata["symbol"]
        try:
            async with AsyncSessionLocal() as db:
                from sqlalchemy import update

                await db.execute(update(MLModel).where(MLModel.symbol == symbol).values(is_active=False))
                for h, hdata in metadata["horizons"].items():
                    for name, m in hdata["models"].items():
                        if "error" in m:
                            continue
                        row = MLModel(
                            id=str(uuid.uuid4()), symbol=symbol, model_type=name,
                            model_version=metadata["trained_at"][:19], model_path=m["artifact"],
                            hyperparameters={**m.get("hyperparameters", {}), "horizon_days": int(h)},
                            feature_columns={"columns": metadata["feature_columns"]},
                            training_period_start=hdata["split"]["train"]["start"],
                            training_period_end=hdata["split"]["train"]["end"],
                            is_active=True,
                        )
                        db.add(row)
                        for split in ("validation", "test"):
                            ev = m[split]
                            db.add(ModelEvaluation(
                                id=str(uuid.uuid4()), model_id=row.id, mae=ev.get("mae"), mse=ev.get("mse"),
                                rmse=ev.get("rmse"), mape=ev.get("mape"), r_squared=ev.get("r_squared"),
                                directional_accuracy=ev.get("directional_accuracy"), evaluation_split=split,
                                evaluation_details=ev,
                            ))
                await db.commit()
        except Exception:
            logger.exception("Could not record training run for %s in the database", symbol)

        best = metadata["horizons"].get("1", {}).get("best_model")
        await self._notify(
            user_id, "training_complete", f"Models trained for {symbol}",
            f"{len(metadata['models_trained'])} models × {len(metadata['horizons'])} horizons trained in "
            f"{metadata['training_seconds']}s. Best 1-day model: {best or 'n/a'}.",
            {"symbol": symbol, "link": f"/predictions?symbol={symbol}"},
        )

    @staticmethod
    async def _notify(user_id: Optional[str], ntype: str, title: str, message: str, payload: dict) -> None:
        if not user_id:
            return
        from app.models import Notification

        try:
            async with AsyncSessionLocal() as db:
                db.add(Notification(id=str(uuid.uuid4()), user_id=user_id, type=ntype, title=title, message=message, payload=payload))
                await db.commit()
        except Exception:
            logger.exception("Could not create notification")


training_jobs = TrainingJobManager()
