from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.services.portfolio_service import replay_transactions


def tx(symbol, kind, qty, price, fees=0.0, day=0):
    when = datetime(2025, 1, 1, tzinfo=timezone.utc) + timedelta(days=day)
    return SimpleNamespace(symbol=symbol, transaction_type=kind, quantity=qty, price=price, fees=fees,
                           transaction_date=when, created_at=when)


def test_average_cost_includes_fees():
    positions, realized = replay_transactions([tx("AAPL", "BUY", 10, 100, fees=10), tx("AAPL", "BUY", 10, 120, day=1)])
    assert positions["AAPL"]["quantity"] == 20
    assert positions["AAPL"]["avg_cost"] == pytest.approx((1000 + 10 + 1200) / 20)
    assert realized == 0


def test_realized_pnl_on_sell():
    positions, realized = replay_transactions([tx("MSFT", "BUY", 10, 100), tx("MSFT", "SELL", 4, 150, fees=2, day=1)])
    assert positions["MSFT"]["quantity"] == 6
    assert positions["MSFT"]["avg_cost"] == pytest.approx(100)  # selling never changes the average cost
    assert realized == pytest.approx(4 * 50 - 2)


def test_full_sell_closes_position():
    positions, _ = replay_transactions([tx("NVDA", "BUY", 5, 100), tx("NVDA", "SELL", 5, 90, day=1)])
    assert "NVDA" not in positions


def test_oversell_raises():
    with pytest.raises(ValueError):
        replay_transactions([tx("AAPL", "BUY", 1, 100), tx("AAPL", "SELL", 2, 100, day=1)])


def test_replay_orders_by_date_not_insertion():
    # A SELL recorded first but dated after the BUY is valid
    positions, _ = replay_transactions([tx("KO", "SELL", 1, 60, day=5), tx("KO", "BUY", 3, 50, day=1)])
    assert positions["KO"]["quantity"] == 2


async def _portfolio_id(c):
    return (await c.get("/api/v1/portfolios")).json()[0]["id"]


async def test_transactions_and_analytics(auth_client):
    pid = await _portfolio_id(auth_client)
    for sym, qty, price in [("AAPL", 10, 150), ("MSFT", 5, 300), ("JPM", 8, 180)]:
        r = await auth_client.post(f"/api/v1/portfolios/{pid}/transactions",
                                   json={"symbol": sym, "transaction_type": "BUY", "quantity": qty, "price": price})
        assert r.status_code == 201, r.text
    a = (await auth_client.get(f"/api/v1/portfolios/{pid}/analytics")).json()
    assert a["total_invested"] == pytest.approx(10 * 150 + 5 * 300 + 8 * 180)
    assert sum(h["weight"] for h in a["holdings"]) == pytest.approx(100, abs=0.1)
    assert a["portfolio_volatility"] > 0
    assert a["var_95"] > 0 and a["cvar_95"] >= a["var_95"]  # expected shortfall is never below VaR
    assert a["max_drawdown"] <= 0
    assert a["beta"] is not None and a["sharpe_ratio"] is not None
    assert len(a["performance"]) > 50
    assert a["is_demo"] is True


async def test_oversell_and_unknown_symbol_rejected(auth_client):
    pid = await _portfolio_id(auth_client)
    await auth_client.post(f"/api/v1/portfolios/{pid}/transactions", json={"symbol": "AAPL", "transaction_type": "BUY", "quantity": 1, "price": 100})
    over = await auth_client.post(f"/api/v1/portfolios/{pid}/transactions", json={"symbol": "AAPL", "transaction_type": "SELL", "quantity": 5, "price": 100})
    assert over.status_code == 400
    unknown = await auth_client.post(f"/api/v1/portfolios/{pid}/transactions", json={"symbol": "NOTAREALTICKER", "transaction_type": "BUY", "quantity": 1, "price": 1})
    assert unknown.status_code in (400, 422)


async def test_delete_transaction_rebuilds_holdings(auth_client):
    pid = await _portfolio_id(auth_client)
    await auth_client.post(f"/api/v1/portfolios/{pid}/transactions", json={"symbol": "KO", "transaction_type": "BUY", "quantity": 4, "price": 60})
    txs = (await auth_client.get(f"/api/v1/portfolios/{pid}/transactions")).json()
    r = await auth_client.delete(f"/api/v1/portfolios/{pid}/transactions/{txs[0]['id']}")
    assert r.status_code == 204
    holdings = (await auth_client.get(f"/api/v1/portfolios/{pid}/holdings")).json()
    assert all(h["symbol"] != "KO" for h in holdings)


async def test_cannot_access_other_users_portfolio(auth_client, client):
    pid = await _portfolio_id(auth_client)
    reg = await client.post("/api/v1/auth/register", json={"email": "intruder@example.com", "password": "TestPass1"})
    r = await client.get(f"/api/v1/portfolios/{pid}", headers={"Authorization": f"Bearer {reg.json()['access_token']}"})
    assert r.status_code == 404
