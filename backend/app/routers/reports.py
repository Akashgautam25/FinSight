"""
FinSight AI — Research Reports Router
"""

import os

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import select

from app.dependencies import CurrentUser, DBSession
from app.models import ResearchReport
from app.schemas.ai import GenerateReportRequest
from app.services.report_service import ReportService

router = APIRouter()


def _serialize(r: ResearchReport, full: bool = True) -> dict:
    data = {"id": r.id, "symbol": r.symbol, "title": r.title, "status": r.status, "generated_at": r.generated_at,
            "pdf_available": bool(r.pdf_path and os.path.exists(r.pdf_path))}
    if full:
        data["report_data"] = r.report_data
    return data


async def _owned(db, report_id: str, user_id: str) -> ResearchReport:
    r = (await db.execute(select(ResearchReport).where(ResearchReport.id == report_id, ResearchReport.user_id == user_id))).scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="Report not found")
    return r


@router.get("")
async def list_reports(current_user: CurrentUser, db: DBSession):
    rows = (await db.execute(
        select(ResearchReport).where(ResearchReport.user_id == current_user.id).order_by(ResearchReport.generated_at.desc())
    )).scalars().all()
    return [_serialize(r) for r in rows]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_report(payload: GenerateReportRequest, current_user: CurrentUser, db: DBSession):
    return await ReportService(db).generate(payload, current_user.id)


@router.get("/{report_id}")
async def get_report(report_id: str, current_user: CurrentUser, db: DBSession):
    return _serialize(await _owned(db, report_id, current_user.id))


@router.get("/{report_id}/export")
async def export_report(report_id: str, current_user: CurrentUser, db: DBSession):
    r = await _owned(db, report_id, current_user.id)
    if not r.pdf_path or not os.path.exists(r.pdf_path):
        raise HTTPException(status_code=404, detail="PDF not available")
    return FileResponse(r.pdf_path, media_type="application/pdf", filename=f"FinSight_{r.symbol}_{r.generated_at:%Y%m%d}.pdf")


@router.delete("/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_report(report_id: str, current_user: CurrentUser, db: DBSession):
    r = await _owned(db, report_id, current_user.id)
    if r.pdf_path and os.path.exists(r.pdf_path):
        os.remove(r.pdf_path)
    await db.delete(r)
    await db.commit()
