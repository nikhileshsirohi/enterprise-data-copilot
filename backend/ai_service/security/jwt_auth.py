from dataclasses import dataclass
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.ai_service.security.rate_limit import enforce_user_rate_limit
from backend.shared.config import get_settings
from backend.shared.django import ensure_django_setup

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class AuthenticatedUser:
    user_id: int
    username: str
    is_staff: bool
    is_superuser: bool = False


def require_authenticated_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> AuthenticatedUser:
    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer access token is required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = _decode_access_token(credentials.credentials)
    user_id = _get_user_id(payload)
    user = _load_active_user(user_id)
    enforce_user_rate_limit(user)
    return user


def require_staff_user(
    current_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
) -> AuthenticatedUser:
    if not current_user.is_staff:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Staff access is required.",
        )
    return current_user


def _decode_access_token(token: str) -> dict:
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.app_secret_key,
            algorithms=["HS256"],
            options={"require": ["exp", "token_type", "user_id"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token has expired.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access token.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    if payload.get("token_type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token is required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload


def _get_user_id(payload: dict) -> int:
    try:
        return int(payload["user_id"])
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access token subject.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def _load_active_user(user_id: int) -> AuthenticatedUser:
    ensure_django_setup()

    from django.contrib.auth import get_user_model
    from django.db import close_old_connections

    close_old_connections()
    try:
        user = get_user_model().objects.filter(id=user_id, is_active=True).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authenticated user was not found.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return AuthenticatedUser(
            user_id=user.id,
            username=user.username,
            is_staff=user.is_staff,
            is_superuser=user.is_superuser,
        )
    finally:
        close_old_connections()
