"""
FinSight AI — Auth Router
register · login · refresh · logout · me (get/update) · preferences ·
change-password · forgot-password · reset-password
"""

import logging
import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.config import settings
from app.dependencies import CurrentUser, DBSession
from app.models import Portfolio, User, UserPreferences, UserProfile, Watchlist, WatchlistStock
from app.schemas.auth import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    PreferencesResponse,
    RefreshTokenRequest,
    ResetPasswordRequest,
    TokenResponse,
    UpdatePreferencesRequest,
    UpdateProfileRequest,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)
from app.utils.auth_utils import (
    create_access_token,
    create_password_reset_token,
    create_refresh_token,
    decode_reset_token_subject,
    hash_password,
    verify_password,
    verify_password_reset_token,
    verify_refresh_token,
)
from app.utils.email import send_email, smtp_configured

router = APIRouter()
logger = logging.getLogger("finsight.auth")

STARTER_WATCHLIST = ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN"]


def _tokens(user_id: str) -> TokenResponse:
    return TokenResponse(access_token=create_access_token(user_id), refresh_token=create_refresh_token(user_id))


async def _user_response(db, user: User) -> UserResponse:
    profile = (await db.execute(select(UserProfile).where(UserProfile.user_id == user.id))).scalar_one_or_none()
    return UserResponse(
        id=user.id, email=user.email, is_active=user.is_active, is_verified=user.is_verified, role=user.role,
        full_name=profile.full_name if profile else None, bio=profile.bio if profile else None,
        default_currency=(profile.default_currency if profile else None) or "USD",
        timezone=(profile.timezone if profile else None) or "UTC",
        created_at=user.created_at,
    )


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: UserRegisterRequest, db: DBSession):
    email = payload.email.lower()
    if (await db.execute(select(User).where(User.email == email))).scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(id=str(uuid.uuid4()), email=email, hashed_password=hash_password(payload.password))
    db.add(user)
    db.add(UserProfile(id=str(uuid.uuid4()), user_id=user.id, full_name=payload.full_name))
    db.add(UserPreferences(id=str(uuid.uuid4()), user_id=user.id, theme="dark", default_market="US"))
    # Starter workspace so every page has something to show
    db.add(Portfolio(id=str(uuid.uuid4()), user_id=user.id, name="My Portfolio", currency="USD", is_default=True,
                     description="Default portfolio"))
    wl = Watchlist(id=str(uuid.uuid4()), user_id=user.id, name="My Watchlist", is_default=True)
    db.add(wl)
    for i, sym in enumerate(STARTER_WATCHLIST):
        db.add(WatchlistStock(id=str(uuid.uuid4()), watchlist_id=wl.id, symbol=sym, sort_order=i))
    await db.commit()
    return _tokens(user.id)


@router.post("/login", response_model=TokenResponse)
async def login(payload: UserLoginRequest, db: DBSession):
    user = (await db.execute(select(User).where(User.email == payload.email.lower()))).scalar_one_or_none()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is deactivated")
    return _tokens(user.id)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(payload: RefreshTokenRequest, db: DBSession):
    data = verify_refresh_token(payload.refresh_token)
    if not data:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")
    user = (await db.execute(select(User).where(User.id == data["sub"]))).scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found")
    return _tokens(user.id)


@router.post("/logout")
async def logout(_: CurrentUser):
    # Tokens are stateless JWTs; the client discards them. (A Redis deny-list could revoke them server-side.)
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: CurrentUser, db: DBSession):
    return await _user_response(db, current_user)


@router.patch("/me", response_model=UserResponse)
async def update_me(payload: UpdateProfileRequest, current_user: CurrentUser, db: DBSession):
    profile = (await db.execute(select(UserProfile).where(UserProfile.user_id == current_user.id))).scalar_one_or_none()
    if not profile:
        profile = UserProfile(id=str(uuid.uuid4()), user_id=current_user.id)
        db.add(profile)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(profile, field, value)
    await db.commit()
    return await _user_response(db, current_user)


@router.get("/me/preferences", response_model=PreferencesResponse)
async def get_preferences(current_user: CurrentUser, db: DBSession):
    prefs = (await db.execute(select(UserPreferences).where(UserPreferences.user_id == current_user.id))).scalar_one_or_none()
    return PreferencesResponse.model_validate(prefs) if prefs else PreferencesResponse()


@router.put("/me/preferences", response_model=PreferencesResponse)
async def update_preferences(payload: UpdatePreferencesRequest, current_user: CurrentUser, db: DBSession):
    prefs = (await db.execute(select(UserPreferences).where(UserPreferences.user_id == current_user.id))).scalar_one_or_none()
    if not prefs:
        prefs = UserPreferences(id=str(uuid.uuid4()), user_id=current_user.id)
        db.add(prefs)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(prefs, field, value)
    await db.commit()
    await db.refresh(prefs)
    return PreferencesResponse.model_validate(prefs)


@router.post("/change-password")
async def change_password(payload: ChangePasswordRequest, current_user: CurrentUser, db: DBSession):
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    current_user.hashed_password = hash_password(payload.new_password)
    await db.commit()
    return {"message": "Password updated"}


@router.post("/forgot-password")
async def forgot_password(payload: ForgotPasswordRequest, db: DBSession):
    """Issue a single-use, 30-minute reset token.

    With SMTP configured the link is emailed. In development (no SMTP) the link is
    returned in the response so the flow can be demonstrated end-to-end.
    """
    generic = {"message": "If an account exists for this email, a password reset link has been sent."}
    user = (await db.execute(select(User).where(User.email == payload.email.lower()))).scalar_one_or_none()
    if not user:
        return generic

    token = create_password_reset_token(user.id, user.hashed_password)
    link = f"{settings.frontend_url.rstrip('/')}/reset-password?token={token}"
    sent = await send_email(
        user.email, "Reset your FinSight AI password",
        f"Use this link within {settings.password_reset_expire_minutes} minutes to reset your password:\n\n{link}\n\n"
        "If you did not request this, you can ignore this email.",
    )
    if sent:
        return generic
    if not settings.is_production and not smtp_configured():
        logger.info("Password reset link for %s: %s", user.email, link)
        return {**generic, "dev_reset_link": link, "note": "SMTP is not configured — the link is shown here for development only."}
    return generic


@router.post("/reset-password")
async def reset_password(payload: ResetPasswordRequest, db: DBSession):
    user_id = decode_reset_token_subject(payload.token)
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none() if user_id else None
    if not user or not verify_password_reset_token(payload.token, user.hashed_password):
        raise HTTPException(status_code=400, detail="This reset link is invalid, expired or has already been used")
    user.hashed_password = hash_password(payload.new_password)
    await db.commit()
    return {"message": "Password reset successfully. You can now sign in."}
