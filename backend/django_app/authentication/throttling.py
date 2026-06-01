from redis.exceptions import RedisError
from rest_framework.throttling import BaseThrottle

from backend.shared.config import get_settings
from backend.shared.redis_client import get_redis_client


class RedisUserRateThrottle(BaseThrottle):
    def __init__(self) -> None:
        self.wait_seconds = 0

    def allow_request(self, request, view) -> bool:
        settings = get_settings()
        key = self._cache_key(request)

        try:
            redis_client = get_redis_client()
            count = redis_client.incr(key)
            if count == 1:
                redis_client.expire(key, settings.api_rate_limit_window_seconds)
            if count > settings.api_rate_limit_requests:
                ttl = redis_client.ttl(key)
                self.wait_seconds = max(int(ttl), 0)
                return False
        except RedisError:
            return True

        return True

    def wait(self) -> int:
        return self.wait_seconds

    def _cache_key(self, request) -> str:
        if request.user and request.user.is_authenticated:
            return f"rate:user:{request.user.id}"

        forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()
        else:
            client_ip = request.META.get("REMOTE_ADDR", "unknown")

        return f"rate:anon:{client_ip}"
