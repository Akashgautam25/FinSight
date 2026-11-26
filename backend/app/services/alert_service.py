"""
FinSight AI — Price Alert Evaluation

Alert types
  price_above      last price ≥ target
  price_below      last price ≤ target
  pct_change_up    today's change ≥ +target %
  pct_change_down  today's change ≤ −target %

A background loop (started in app.main) checks all active alerts every
ALERT_CHECK_INTERVAL_SECONDS using one batched quote request, marks triggered
alerts and creates in-app notifications.
"""

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select

from app.data import market_data as md
from app.database import AsyncSessionLocal
from app.models import Notification, PriceAlert

logger = logging.getLogger("finsight.alerts")

ALERT_TYPES = {"price_above", "price_below", "pct_change_up", "pct_change_down"}


def is_triggered(alert_type: str, target: float, quote: dict) -> bool:
    price, change = quote.get("price"), quote.get("change_pct")
    if alert_type == "price_above":
        return price is not None and price >= target
    if alert_type == "price_below":
        return price is not None and price <= target
    if alert_type == "pct_change_up":
        return change is not None and change >= abs(target)
    if alert_type == "pct_change_down":
        return change is not None and change <= -abs(target)
    return False


def describe(alert_type: str, symbol: str, target: float) -> str:
    return {
        "price_above": f"{symbol} price rises above {target:,.2f}",
        "price_below": f"{symbol} price falls below {target:,.2f}",
        "pct_change_up": f"{symbol} gains {abs(target):.2f}% or more in a day",
        "pct_change_down": f"{symbol} drops {abs(target):.2f}% or more in a day",
    }.get(alert_type, f"{symbol} {alert_type} {target}")


async def check_alerts(user_id: Optional[str] = None) -> int:
    """Evaluate active alerts (optionally only one user's). Returns the number triggered."""
    async with AsyncSessionLocal() as db:
        query = select(PriceAlert).where(PriceAlert.is_active.is_(True), PriceAlert.is_triggered.is_(False))
        if user_id:
            query = query.where(PriceAlert.user_id == user_id)
        alerts = list((await db.execute(query)).scalars().all())
        if not alerts:
            return 0

        quotes = await md.aquotes(sorted({a.symbol for a in alerts}))
        triggered = 0
        now = datetime.now(timezone.utc)
        for alert in alerts:
            q = quotes.get(alert.symbol)
            if not q or not is_triggered(alert.alert_type, float(alert.target_value), q):
                continue
            alert.is_triggered, alert.is_active, alert.triggered_at = True, False, now
            db.add(Notification(
                id=str(uuid.uuid4()), user_id=alert.user_id, type="price_alert",
                title=f"Alert triggered: {alert.symbol}",
                message=f"{describe(alert.alert_type, alert.symbol, float(alert.target_value))} — now {q['price']:,.2f} ({q['change_pct']:+.2f}% today)"
                        + (" [simulated data]" if q.get("is_demo") else ""),
                payload={"symbol": alert.symbol, "alert_id": alert.id, "price": q["price"], "link": f"/stocks/{alert.symbol}"},
            ))
            triggered += 1
        await db.commit()
        return triggered


async def alert_loop(interval_seconds: int) -> None:
    await asyncio.sleep(15)  # let the app finish starting
    while True:
        try:
            n = await check_alerts()
            if n:
                logger.info("Triggered %d price alert(s)", n)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Alert check failed")
        await asyncio.sleep(interval_seconds)
