"""
FinSight AI — Portfolio Router
"""

import uuid
from typing import Annotated, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.dependencies import CurrentUser, DBSession
from app.models import Portfolio, PortfolioHolding, PortfolioTransaction
from app.schemas.portfolio import (
    CreatePortfolioRequest, AddTransactionRequest,
    PortfolioResponse, PortfolioAnalyticsResponse, HoldingResponse,
)
from app.services.portfolio_service import PortfolioService

router = APIRouter()


@router.get("", response_model=List[PortfolioResponse])
async def list_portfolios(current_user: CurrentUser, db: DBSession):
    result = await db.execute(
        select(Portfolio).where(Portfolio.user_id == current_user.id)
    )
    return result.scalars().all()


@router.post("", response_model=PortfolioResponse, status_code=status.HTTP_201_CREATED)
async def create_portfolio(
    payload: CreatePortfolioRequest,
    current_user: CurrentUser,
    db: DBSession,
):
    portfolio = Portfolio(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        name=payload.name,
        description=payload.description,
        currency=payload.currency,
    )
    db.add(portfolio)
    await db.commit()
    await db.refresh(portfolio)
    return portfolio


@router.get("/{portfolio_id}", response_model=PortfolioResponse)
async def get_portfolio(portfolio_id: str, current_user: CurrentUser, db: DBSession):
    result = await db.execute(
        select(Portfolio).where(
            Portfolio.id == portfolio_id,
            Portfolio.user_id == current_user.id,
        )
    )
    portfolio = result.scalar_one_or_none()
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    return portfolio


@router.delete("/{portfolio_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_portfolio(portfolio_id: str, current_user: CurrentUser, db: DBSession):
    result = await db.execute(
        select(Portfolio).where(
            Portfolio.id == portfolio_id,
            Portfolio.user_id == current_user.id,
        )
    )
    portfolio = result.scalar_one_or_none()
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    await db.delete(portfolio)
    await db.commit()


@router.post("/{portfolio_id}/transactions", status_code=status.HTTP_201_CREATED)
async def add_transaction(
    portfolio_id: str,
    payload: AddTransactionRequest,
    current_user: CurrentUser,
    db: DBSession,
):
    result = await db.execute(
        select(Portfolio).where(
            Portfolio.id == portfolio_id,
            Portfolio.user_id == current_user.id,
        )
    )
    portfolio = result.scalar_one_or_none()
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    service = PortfolioService(db)
    return await service.add_transaction(portfolio, payload)


@router.get("/{portfolio_id}/holdings", response_model=List[HoldingResponse])
async def get_holdings(portfolio_id: str, current_user: CurrentUser, db: DBSession):
    result = await db.execute(
        select(Portfolio).where(
            Portfolio.id == portfolio_id,
            Portfolio.user_id == current_user.id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Portfolio not found")

    service = PortfolioService(db)
    return await service.get_holdings_with_prices(portfolio_id)


@router.get("/{portfolio_id}/analytics", response_model=PortfolioAnalyticsResponse)
async def get_analytics(portfolio_id: str, current_user: CurrentUser, db: DBSession):
    result = await db.execute(
        select(Portfolio).where(
            Portfolio.id == portfolio_id,
            Portfolio.user_id == current_user.id,
        )
    )
    portfolio = result.scalar_one_or_none()
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    service = PortfolioService(db)
    return await service.compute_analytics(portfolio)
