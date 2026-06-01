from hashlib import sha256
from uuid import uuid4

from rest_framework_simplejwt.tokens import RefreshToken

from backend.shared.config import get_settings
from backend.shared.redis_client import get_redis_client


def track_login_session(user_id: int, username: str, refresh_token: str) -> str:
    settings = get_settings()
    redis_client = get_redis_client()
    refresh = RefreshToken(refresh_token)
    session_id = str(uuid4())
    refresh_jti = str(refresh["jti"])
    refresh_hash = sha256(refresh_token.encode("utf-8")).hexdigest()

    session_key = f"auth:session:{session_id}"
    refresh_key = f"auth:refresh:{user_id}:{refresh_jti}"

    pipeline = redis_client.pipeline()
    pipeline.hset(
        session_key,
        mapping={
            "user_id": str(user_id),
            "username": username,
            "refresh_jti": refresh_jti,
            "refresh_hash": refresh_hash,
        },
    )
    pipeline.expire(session_key, settings.jwt_refresh_token_ttl_seconds)
    pipeline.set(refresh_key, session_id, ex=settings.jwt_refresh_token_ttl_seconds)
    pipeline.execute()

    return session_id


def is_refresh_token_active(refresh_token: str) -> bool:
    refresh = RefreshToken(refresh_token)
    user_id = refresh["user_id"]
    refresh_jti = refresh["jti"]
    refresh_key = f"auth:refresh:{user_id}:{refresh_jti}"
    return bool(get_redis_client().exists(refresh_key))


def revoke_login_session(refresh_token: str | None, session_id: str | None) -> None:
    redis_client = get_redis_client()
    keys = []

    if refresh_token:
        refresh = RefreshToken(refresh_token)
        keys.append(f"auth:refresh:{refresh['user_id']}:{refresh['jti']}")

    if session_id:
        keys.append(f"auth:session:{session_id}")

    if keys:
        redis_client.delete(*keys)
