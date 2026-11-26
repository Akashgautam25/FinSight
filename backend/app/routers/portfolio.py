"""
FinSight AI — Portfolio Router
"""

import uuid
from typing import List

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.dependencies import CurrentUser, DBSession
from app.models import Portfolio, PortfolioTransaction
from app.schemas.portfolio import (
    AddTransactionRequest,
    CreatePortfolioRequest,
    HoldingResponse,
    PortfolioAnalyticsResponse,
    PortfolioResponse,
    TransactionResponse,
    UpdatePortfolioRequest,
)
from app.services.portfolio_service import PortfolioService

router = APIRouter()


async def _owned(db, portfolio_id: str, user_id: str) -> Portfolio:
    portfolio = (await db.execute(
        select(Portfolio).where(Portfolio.id == portfolio_id, Portfolio.user_id == user_id)
    )).scalar_one_or_none()
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    return portfolio


@router.get("", response_model=List[PortfolioResponse])
async def list_portfolios(current_user: CurrentUser, db: DBSession):
    result = await db.execute(
        select(Portfolio).where(Portfolio.user_id == current_user.id).order_by(Portfolio.is_default.desc(), Portfolio.created_at)
    )
    return result.scalars().all()


@router.post("", response_model=PortfolioResponse, status_code=status.HTTP_201_CREATED)
async def create_portfolio(payload: CreatePortfolioRequest, current_user: CurrentUser, db: DBSession):
    has_any = (await db.execute(select(Portfolio.id).where(Portfolio.user_id == current_user.id))).first()
    portfolio = Portfolio(id=str(uuid.uuid4()), user_id=current_user.id, name=payload.name.strip(),
                          description=payload.description, currency=payload.currency, is_default=not has_any)
    db.add(portfolio)
    await db.commit()
    await db.refresh(portfolio)
    return portfolio


@router.get("/{portfolio_id}", response_model=PortfolioResponse)
async def get_portfolio(portfolio_id: str, current_user: CurrentUser, db: DBSession):
    return await _owned(db, portfolio_id, current_user.id)


@router.patch("/{portfolio_id}", response_model=PortfolioResponse)
async def update_portfolio(portfolio_id: str, payload: UpdatePortfolioRequest, current_user: CurrentUser, db: DBSession):
    portfolio = await _owned(db, portfolio_id, current_user.id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(portfolio, field, value)
    await db.commit()
    await db.refresh(portfolio)
    return portfolio


@router.delete("/{portfolio_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_portfolio(portfolio_id: str, current_user: CurrentUser, db: DBSession):
    portfolio = await _owned(db, portfolio_id, current_user.id)
    await db.delete(portfolio)
    await db.commit()


@router.post("/{portfolio_id}/transactions", status_code=status.HTTP_201_CREATED)
async def add_transaction(portfolio_id: str, payload: AddTransactionRequest, current_user: CurrentUser, db: DBSession):
    portfolio = await _owned(db, portfolio_id, current_user.id)
    return await PortfolioService(db).add_transaction(portfolio, payload)


@router.get("/{portfolio_id}/transactions", response_model=List[TransactionResponse])
async def list_transactions(portfolio_id: str, current_user: CurrentUser, db: DBSession):
    await _owned(db, portfolio_id, current_user.id)
    result = await db.execute(
        select(PortfolioTransaction).where(PortfolioTransaction.portfolio_id == portfolio_id)
        .order_by(PortfolioTransaction.transaction_date.desc(), PortfolioTransaction.created_at.desc())
    )
    return result.scalars().all()


@router.delete("/{portfolio_id}/transactions/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_transaction(portfolio_id: str, transaction_id: str, current_user: CurrentUser, db: DBSession):
    portfolio = await _owned(db, portfolio_id, current_user.id)
    await PortfolioService(db).delete_transaction(portfolio, transaction_id)


@router.get("/{portfolio_id}/holdings", response_model=List[HoldingResponse])
async def get_holdings(portfolio_id: str, current_user: CurrentUser, db: DBSession):
    await _owned(db, portfolio_id, current_user.id)
    return await PortfolioService(db).get_holdings_with_prices(portfolio_id)


@router.get("/{portfolio_id}/analytics", response_model=PortfolioAnalyticsResponse)
async def get_analytics(portfolio_id: str, current_user: CurrentUser, db: DBSession):
    portfolio = await _owned(db, portfolio_id, current_user.id)
    return await PortfolioService(db).compute_analytics(portfolio)
