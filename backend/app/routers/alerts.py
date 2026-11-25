"""
FinSight AI — Alerts Router
"""

import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.dependencies import CurrentUser, DBSession
from app.models import PriceAlert
from app.schemas.ai import OptimizationRequest  # re-use base

from pydantic import BaseModel
from typing import Optional


class CreateAlertRequest(BaseModel):
    symbol: str
    alert_type: str  # price_above, price_below, pct_change_up, pct_change_down
    target_value: float
    condition: str  # above / below


router = APIRouter()


@router.get("")
async def list_alerts(current_user: CurrentUser, db: DBSession):
    result = await db.execute(
        select(PriceAlert)
        .where(PriceAlert.user_id == current_user.id, PriceAlert.is_active == True)
        .order_by(PriceAlert.created_at.desc())
    )
    return result.scalars().all()


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_alert(
    payload: CreateAlertRequest,
    current_user: CurrentUser,
    db: DBSession,
):
    alert = PriceAlert(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        symbol=payload.symbol.upper(),
        alert_type=payload.alert_type,
        target_value=payload.target_value,
        condition=payload.condition,
    )
    db.add(alert)
    await db.commit()
    await db.refresh(alert)
    return alert


@router.delete("/{alert_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_alert(alert_id: str, current_user: CurrentUser, db: DBSession):
    result = await db.execute(
        select(PriceAlert).where(
            PriceAlert.id == alert_id,
            PriceAlert.user_id == current_user.id,
        )
    )
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    await db.delete(alert)
    await db.commit()
