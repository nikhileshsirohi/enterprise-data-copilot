from fastapi import HTTPException
from redis.exceptions import RedisError

from backend.ai_service.security.jwt_auth import AuthenticatedUser
from backend.ai_service.security.rate_limit import RedisUserRateLimiter, enforce_user_rate_limit


class FakeRedis:
    def __init__(self) -> None:
        self.values = {}
        self.expirations = {}

    def incr(self, key):
        self.values[key] = self.values.get(key, 0) + 1
        return self.values[key]

    def expire(self, key, seconds):
        self.expirations[key] = seconds

    def ttl(self, key):
        return self.expirations.get(key, 0)


class FailingRedis:
    def incr(self, key):
        raise RedisError("redis unavailable")


def build_user() -> AuthenticatedUser:
    return AuthenticatedUser(user_id=7, username="rate-user", is_staff=False)


def test_redis_user_rate_limiter_allows_request_under_limit() -> None:
    redis = FakeRedis()
    limiter = RedisUserRateLimiter(redis_client=redis)

    result = limiter.check(build_user())

    assert result.allowed is True
    assert redis.values["rate:fastapi:user:7"] == 1
    assert redis.expirations["rate:fastapi:user:7"] == 60


def test_redis_user_rate_limiter_blocks_when_limit_exceeded() -> None:
    redis = FakeRedis()
    redis.values["rate:fastapi:user:7"] = 120
    redis.expirations["rate:fastapi:user:7"] = 42
    limiter = RedisUserRateLimiter(redis_client=redis)

    result = limiter.check(build_user())

    assert result.allowed is False
    assert result.retry_after_seconds == 42


def test_enforce_user_rate_limit_raises_429_when_blocked() -> None:
    redis = FakeRedis()
    redis.values["rate:fastapi:user:7"] = 120
    redis.expirations["rate:fastapi:user:7"] = 42

    try:
        enforce_user_rate_limit(build_user(), RedisUserRateLimiter(redis_client=redis))
    except HTTPException as exc:
        assert exc.status_code == 429
        assert exc.headers == {"Retry-After": "42"}
    else:
        raise AssertionError("Expected HTTPException")


def test_redis_user_rate_limiter_fails_open_when_redis_is_unavailable() -> None:
    limiter = RedisUserRateLimiter(redis_client=FailingRedis())

    result = limiter.check(build_user())

    assert result.allowed is True
