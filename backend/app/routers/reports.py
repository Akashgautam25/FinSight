"""
FinSight AI — Reports Router
"""

import uuid
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select

from app.dependencies import CurrentUser, DBSession
from app.models import ResearchReport

router = APIRouter()


@router.get("")
async def list_reports(current_user: CurrentUser, db: DBSession):
    result = await db.execute(
        select(ResearchReport)
        .where(ResearchReport.user_id == current_user.id)
        .order_by(ResearchReport.generated_at.desc())
    )
    return result.scalars().all()


@router.get("/{report_id}")
async def get_report(report_id: str, current_user: CurrentUser, db: DBSession):
    result = await db.execute(
        select(ResearchReport).where(
            ResearchReport.id == report_id,
            ResearchReport.user_id == current_user.id,
        )
    )
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report


@router.get("/{report_id}/export")
async def export_report(report_id: str, current_user: CurrentUser, db: DBSession):
    result = await db.execute(
        select(ResearchReport).where(
            ResearchReport.id == report_id,
            ResearchReport.user_id == current_user.id,
        )
    )
    report = result.scalar_one_or_none()
    if not report or not report.pdf_path:
        raise HTTPException(status_code=404, detail="PDF not available")
    return FileResponse(
        report.pdf_path,
        media_type="application/pdf",
        filename=f"finsight_report_{report.symbol}.pdf",
    )
