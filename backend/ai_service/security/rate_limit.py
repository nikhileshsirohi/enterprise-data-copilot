from dataclasses import dataclass

from fastapi import HTTPException, status
from redis import Redis
from redis.exceptions import RedisError

from backend.shared.config import get_settings
from backend.shared.redis_client import get_redis_client


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    retry_after_seconds: int = 0


class RedisUserRateLimiter:
    def __init__(self, redis_client: Redis | None = None) -> None:
        self.redis_client = redis_client or get_redis_client()

    def check(self, user) -> RateLimitResult:
        settings = get_settings()
        key = f"rate:fastapi:user:{user.user_id}"

        try:
            count = self.redis_client.incr(key)
            if count == 1:
                self.redis_client.expire(key, settings.api_rate_limit_window_seconds)
            if count > settings.api_rate_limit_requests:
                ttl = self.redis_client.ttl(key)
                return RateLimitResult(
                    allowed=False,
                    retry_after_seconds=max(int(ttl), 0),
                )
        except RedisError:
            return RateLimitResult(allowed=True)

        return RateLimitResult(allowed=True)


def enforce_user_rate_limit(user, limiter: RedisUserRateLimiter | None = None) -> None:
    result = (limiter or RedisUserRateLimiter()).check(user)
    if result.allowed:
        return

    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="Rate limit exceeded.",
        headers={"Retry-After": str(result.retry_after_seconds)},
    )
