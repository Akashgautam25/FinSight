"""
FinSight AI — Auth Router
Handles: register, login, refresh, logout, forgot/reset password, me
"""

import uuid
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import User, UserProfile
from app.schemas.auth import (
    UserRegisterRequest, UserLoginRequest, RefreshTokenRequest,
    TokenResponse, UserResponse, UpdateProfileRequest, ForgotPasswordRequest,
    ResetPasswordRequest,
)
from app.utils.auth_utils import (
    hash_password, verify_password,
    create_access_token, create_refresh_token, verify_refresh_token,
)
from app.dependencies import CurrentUser

router = APIRouter()


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: UserRegisterRequest, db: Annotated[AsyncSession, Depends(get_db)]):
    # Check email uniqueness
    result = await db.execute(select(User).where(User.email == payload.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        id=str(uuid.uuid4()),
        email=payload.email,
        hashed_password=hash_password(payload.password),
    )
    db.add(user)
    await db.flush()

    profile = UserProfile(
        id=str(uuid.uuid4()),
        user_id=user.id,
        full_name=payload.full_name,
    )
    db.add(profile)
    await db.commit()
    await db.refresh(user)

    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


@router.post("/login", response_model=TokenResponse)
async def login(payload: UserLoginRequest, db: Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is deactivated")

    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(payload: RefreshTokenRequest, db: Annotated[AsyncSession, Depends(get_db)]):
    token_data = verify_refresh_token(payload.refresh_token)
    if not token_data:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    result = await db.execute(select(User).where(User.id == token_data["sub"]))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found")

    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


@router.post("/logout")
async def logout():
    # In a full implementation, add the refresh token to a Redis blocklist here
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: CurrentUser):
    return current_user


@router.patch("/me", response_model=UserResponse)
async def update_me(
    payload: UpdateProfileRequest,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(
        select(UserProfile).where(UserProfile.user_id == current_user.id)
    )
    profile = result.scalar_one_or_none()
    if profile:
        for field, value in payload.model_dump(exclude_none=True).items():
            setattr(profile, field, value)
    await db.commit()
    return current_user


@router.post("/forgot-password")
async def forgot_password(payload: ForgotPasswordRequest):
    # In production: generate a time-limited reset token, store in Redis, send email
    return {"message": "If this email exists, a reset link has been sent"}


@router.post("/reset-password")
async def reset_password(payload: ResetPasswordRequest, db: Annotated[AsyncSession, Depends(get_db)]):
    # In production: validate the token from Redis, update password
    return {"message": "Password reset successfully"}
