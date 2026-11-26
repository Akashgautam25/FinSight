"""
FinSight AI — Watchlists Router
"""

import asyncio
import uuid

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.data import market_data as md
from app.dependencies import CurrentUser, DBSession
from app.models import Watchlist, WatchlistStock
from app.services.stock_service import StockService

router = APIRouter()


class WatchlistCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)


class SymbolAdd(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=20)


def _serialize(wl: Watchlist) -> dict:
    return {"id": wl.id, "name": wl.name, "is_default": wl.is_default, "created_at": wl.created_at,
            "symbols": [s.symbol for s in sorted(wl.stocks, key=lambda s: s.sort_order)]}


async def _owned(db, watchlist_id: str, user_id: str) -> Watchlist:
    wl = (await db.execute(
        select(Watchlist).options(selectinload(Watchlist.stocks)).where(Watchlist.id == watchlist_id, Watchlist.user_id == user_id)
    )).scalar_one_or_none()
    if not wl:
        raise HTTPException(status_code=404, detail="Watchlist not found")
    return wl


@router.get("")
async def list_watchlists(current_user: CurrentUser, db: DBSession):
    result = await db.execute(
        select(Watchlist).options(selectinload(Watchlist.stocks)).where(Watchlist.user_id == current_user.id)
        .order_by(Watchlist.is_default.desc(), Watchlist.created_at)
    )
    return [_serialize(w) for w in result.scalars().all()]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_watchlist(payload: WatchlistCreate, current_user: CurrentUser, db: DBSession):
    has_any = (await db.execute(select(Watchlist.id).where(Watchlist.user_id == current_user.id))).first()
    wl = Watchlist(id=str(uuid.uuid4()), user_id=current_user.id, name=payload.name.strip(), is_default=not has_any)
    db.add(wl)
    await db.commit()
    return {"id": wl.id, "name": wl.name, "is_default": wl.is_default, "symbols": []}


@router.patch("/{watchlist_id}")
async def rename_watchlist(watchlist_id: str, payload: WatchlistCreate, current_user: CurrentUser, db: DBSession):
    wl = await _owned(db, watchlist_id, current_user.id)
    wl.name = payload.name.strip()
    await db.commit()
    return _serialize(wl)


@router.delete("/{watchlist_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_watchlist(watchlist_id: str, current_user: CurrentUser, db: DBSession):
    wl = await _owned(db, watchlist_id, current_user.id)
    await db.delete(wl)
    await db.commit()


@router.post("/{watchlist_id}/symbols", status_code=status.HTTP_201_CREATED)
async def add_symbol(watchlist_id: str, payload: SymbolAdd, current_user: CurrentUser, db: DBSession):
    wl = await _owned(db, watchlist_id, current_user.id)
    symbol = payload.symbol.strip().upper()
    if symbol in {s.symbol for s in wl.stocks}:
        raise HTTPException(status_code=409, detail=f"{symbol} is already in this watchlist")
    if symbol not in await md.aquotes([symbol]):
        raise HTTPException(status_code=400, detail=f"Unknown symbol '{symbol}'")
    max_order = (await db.execute(select(func.max(WatchlistStock.sort_order)).where(WatchlistStock.watchlist_id == wl.id))).scalar() or 0
    db.add(WatchlistStock(id=str(uuid.uuid4()), watchlist_id=wl.id, symbol=symbol, sort_order=max_order + 1))
    await db.commit()
    return {"message": f"{symbol} added", "symbol": symbol}


@router.delete("/{watchlist_id}/symbols/{symbol}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_symbol(watchlist_id: str, symbol: str, current_user: CurrentUser, db: DBSession):
    wl = await _owned(db, watchlist_id, current_user.id)
    item = next((s for s in wl.stocks if s.symbol == symbol.upper()), None)
    if not item:
        raise HTTPException(status_code=404, detail="Symbol not in watchlist")
    await db.delete(item)
    await db.commit()


@router.get("/{watchlist_id}/quotes")
async def watchlist_quotes(watchlist_id: str, current_user: CurrentUser, db: DBSession):
    """Watchlist symbols enriched with live quotes and company names."""
    wl = await _owned(db, watchlist_id, current_user.id)
    symbols = [s.symbol for s in sorted(wl.stocks, key=lambda s: s.sort_order)]
    if not symbols:
        return {"id": wl.id, "name": wl.name, "items": []}
    quotes, profiles = await asyncio.gather(md.aquotes(symbols), StockService().get_profiles(symbols))
    items = []
    for sym in symbols:
        prof = profiles.get(sym, {})
        q = quotes.get(sym, {})
        items.append({
            "symbol": sym, "name": prof.get("name", sym), "currency": prof.get("currency", "USD"), "sector": prof.get("sector"),
            "price": q.get("price"), "change": q.get("change"), "change_pct": q.get("change_pct"),
            "volume": q.get("volume"), "is_demo": q.get("is_demo", False),
        })
    return {"id": wl.id, "name": wl.name, "items": items}
