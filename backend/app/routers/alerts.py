"""
FinSight AI — Price Alerts Router
"""

import uuid

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select

from app.data import market_data as md
from app.dependencies import CurrentUser, DBSession
from app.models import PriceAlert
from app.services.alert_service import ALERT_TYPES, check_alerts, describe

router = APIRouter()


class CreateAlertRequest(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=20)
    alert_type: str = Field(..., description="price_above | price_below | pct_change_up | pct_change_down")
    target_value: float = Field(..., gt=0)

    @field_validator("alert_type")
    @classmethod
    def valid_type(cls, v: str) -> str:
        if v not in ALERT_TYPES:
            raise ValueError(f"alert_type must be one of {sorted(ALERT_TYPES)}")
        return v


def _serialize(a: PriceAlert, quote: dict | None = None) -> dict:
    return {
        "id": a.id, "symbol": a.symbol, "alert_type": a.alert_type, "target_value": float(a.target_value),
        "condition": a.condition, "is_active": a.is_active, "is_triggered": a.is_triggered,
        "triggered_at": a.triggered_at, "created_at": a.created_at,
        "description": describe(a.alert_type, a.symbol, float(a.target_value)),
        "current_price": quote.get("price") if quote else None,
        "change_pct": quote.get("change_pct") if quote else None,
    }


@router.get("")
async def list_alerts(current_user: CurrentUser, db: DBSession, include_triggered: bool = Query(True)):
    query = select(PriceAlert).where(PriceAlert.user_id == current_user.id)
    if not include_triggered:
        query = query.where(PriceAlert.is_active.is_(True))
    alerts = list((await db.execute(query.order_by(PriceAlert.created_at.desc()))).scalars().all())
    quotes = await md.aquotes(sorted({a.symbol for a in alerts})) if alerts else {}
    return [_serialize(a, quotes.get(a.symbol)) for a in alerts]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_alert(payload: CreateAlertRequest, current_user: CurrentUser, db: DBSession):
    symbol = payload.symbol.strip().upper()
    quotes = await md.aquotes([symbol])
    if symbol not in quotes:
        raise HTTPException(status_code=400, detail=f"Unknown symbol '{symbol}'")
    alert = PriceAlert(
        id=str(uuid.uuid4()), user_id=current_user.id, symbol=symbol, alert_type=payload.alert_type,
        target_value=payload.target_value, condition="above" if payload.alert_type in ("price_above", "pct_change_up") else "below",
    )
    db.add(alert)
    await db.commit()
    await db.refresh(alert)
    return _serialize(alert, quotes.get(symbol))


@router.post("/check")
async def check_now(current_user: CurrentUser):
    """Evaluate your alerts immediately (the background checker also runs periodically)."""
    triggered = await check_alerts(user_id=current_user.id)
    return {"triggered": triggered}


@router.delete("/{alert_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_alert(alert_id: str, current_user: CurrentUser, db: DBSession):
    alert = (await db.execute(select(PriceAlert).where(PriceAlert.id == alert_id, PriceAlert.user_id == current_user.id))).scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    await db.delete(alert)
    await db.commit()
