"""
FinSight AI — Auth Utilities (JWT tokens, bcrypt password hashing)
"""

import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt

from app.config import settings


# ── Passwords ────────────────────────────────────────────────────────────────

def _prepare(password: str) -> bytes:
    # bcrypt only uses the first 72 bytes; pre-hash longer inputs so they are not truncated.
    raw = password.encode("utf-8")
    if len(raw) > 72:
        raw = hashlib.sha256(raw).hexdigest().encode("ascii")
    return raw


def hash_password(plain_password: str) -> str:
    return bcrypt.hashpw(_prepare(plain_password), bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(_prepare(plain_password), hashed_password.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# ── JWT ──────────────────────────────────────────────────────────────────────

def _encode(payload: dict, expires_in: timedelta) -> str:
    now = datetime.now(timezone.utc)
    payload = {**payload, "iat": now, "exp": now + expires_in, "jti": str(uuid.uuid4())}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def _decode(token: str, expected_type: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    except jwt.PyJWTError:
        return None
    if payload.get("type") != expected_type:
        return None
    return payload


def create_access_token(user_id: str) -> str:
    return _encode(
        {"sub": user_id, "type": "access"},
        timedelta(minutes=settings.access_token_expire_minutes),
    )


def create_refresh_token(user_id: str) -> str:
    return _encode(
        {"sub": user_id, "type": "refresh"},
        timedelta(days=settings.refresh_token_expire_days),
    )


def verify_access_token(token: str) -> Optional[dict]:
    return _decode(token, "access")


def verify_refresh_token(token: str) -> Optional[dict]:
    return _decode(token, "refresh")


def _password_fingerprint(hashed_password: str) -> str:
    # Changes whenever the password changes, which makes reset tokens single-use.
    return hashlib.sha256(hashed_password.encode("utf-8")).hexdigest()[:16]


def create_password_reset_token(user_id: str, hashed_password: str) -> str:
    return _encode(
        {"sub": user_id, "type": "reset", "pwf": _password_fingerprint(hashed_password)},
        timedelta(minutes=settings.password_reset_expire_minutes),
    )


def verify_password_reset_token(token: str, hashed_password: str) -> Optional[dict]:
    payload = _decode(token, "reset")
    if not payload or payload.get("pwf") != _password_fingerprint(hashed_password):
        return None
    return payload


def decode_reset_token_subject(token: str) -> Optional[str]:
    payload = _decode(token, "reset")
    return payload.get("sub") if payload else None
