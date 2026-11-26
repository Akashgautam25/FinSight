from tests.conftest import PASSWORD


async def test_register_returns_tokens(client):
    r = await client.post("/api/v1/auth/register", json={"email": "new@example.com", "password": PASSWORD})
    assert r.status_code == 201
    assert {"access_token", "refresh_token"} <= r.json().keys()


async def test_register_duplicate_email_rejected(client):
    body = {"email": "dup@example.com", "password": PASSWORD}
    await client.post("/api/v1/auth/register", json=body)
    r = await client.post("/api/v1/auth/register", json=body)
    assert r.status_code == 400


async def test_register_rejects_weak_password(client):
    r = await client.post("/api/v1/auth/register", json={"email": "weak@example.com", "password": "short"})
    assert r.status_code == 422


async def test_login_and_wrong_password(client):
    await client.post("/api/v1/auth/register", json={"email": "login@example.com", "password": PASSWORD})
    ok = await client.post("/api/v1/auth/login", json={"email": "LOGIN@example.com", "password": PASSWORD})
    assert ok.status_code == 200
    bad = await client.post("/api/v1/auth/login", json={"email": "login@example.com", "password": "WrongPass1"})
    assert bad.status_code == 401


async def test_protected_route_requires_token(client):
    r = await client.get("/api/v1/portfolios")
    assert r.status_code == 401


async def test_invalid_token_rejected(client):
    r = await client.get("/api/v1/auth/me", headers={"Authorization": "Bearer not-a-jwt"})
    assert r.status_code == 401


async def test_me_and_profile_update(auth_client):
    me = await auth_client.get("/api/v1/auth/me")
    assert me.json()["full_name"] == "Test User"
    upd = await auth_client.patch("/api/v1/auth/me", json={"full_name": "Renamed", "default_currency": "INR"})
    assert upd.json()["full_name"] == "Renamed"
    assert upd.json()["default_currency"] == "INR"


async def test_registration_creates_starter_workspace(auth_client):
    portfolios = (await auth_client.get("/api/v1/portfolios")).json()
    watchlists = (await auth_client.get("/api/v1/watchlists")).json()
    assert len(portfolios) == 1 and portfolios[0]["is_default"]
    assert len(watchlists) == 1 and len(watchlists[0]["symbols"]) == 5


async def test_refresh_token(client):
    reg = await client.post("/api/v1/auth/register", json={"email": "refresh@example.com", "password": PASSWORD})
    r = await client.post("/api/v1/auth/refresh", json={"refresh_token": reg.json()["refresh_token"]})
    assert r.status_code == 200
    # an access token must not work as a refresh token
    bad = await client.post("/api/v1/auth/refresh", json={"refresh_token": reg.json()["access_token"]})
    assert bad.status_code == 401


async def test_password_reset_flow_is_single_use(client):
    await client.post("/api/v1/auth/register", json={"email": "reset@example.com", "password": PASSWORD})
    fp = (await client.post("/api/v1/auth/forgot-password", json={"email": "reset@example.com"})).json()
    token = fp["dev_reset_link"].split("token=")[1]
    ok = await client.post("/api/v1/auth/reset-password", json={"token": token, "new_password": "NewPass123"})
    assert ok.status_code == 200
    reuse = await client.post("/api/v1/auth/reset-password", json={"token": token, "new_password": "Another123"})
    assert reuse.status_code == 400
    login = await client.post("/api/v1/auth/login", json={"email": "reset@example.com", "password": "NewPass123"})
    assert login.status_code == 200


async def test_forgot_password_does_not_reveal_unknown_emails(client):
    r = await client.post("/api/v1/auth/forgot-password", json={"email": "nobody@example.com"})
    assert r.status_code == 200 and "dev_reset_link" not in r.json()


async def test_change_password(auth_client):
    bad = await auth_client.post("/api/v1/auth/change-password", json={"current_password": "nope", "new_password": "Changed123"})
    assert bad.status_code == 400
    ok = await auth_client.post("/api/v1/auth/change-password", json={"current_password": PASSWORD, "new_password": "Changed123"})
    assert ok.status_code == 200
