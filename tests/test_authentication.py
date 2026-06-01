import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from backend.django_app.authentication import services


class FakePipeline:
    def __init__(self, redis_client):
        self.redis_client = redis_client
        self.operations = []

    def hset(self, key, mapping):
        self.operations.append(("hset", key, mapping))
        return self

    def expire(self, key, seconds):
        self.operations.append(("expire", key, seconds))
        return self

    def set(self, key, value, ex=None):
        self.operations.append(("set", key, value, ex))
        return self

    def execute(self):
        for operation in self.operations:
            if operation[0] == "hset":
                _name, key, mapping = operation
                self.redis_client.hashes[key] = mapping
            elif operation[0] == "set":
                _name, key, value, _ex = operation
                self.redis_client.values[key] = value


class FakeRedis:
    def __init__(self):
        self.hashes = {}
        self.values = {}

    def pipeline(self):
        return FakePipeline(self)

    def exists(self, key):
        return int(key in self.values or key in self.hashes)

    def delete(self, *keys):
        for key in keys:
            self.values.pop(key, None)
            self.hashes.pop(key, None)


@pytest.mark.django_db
def test_login_tracks_refresh_token_in_redis(client, monkeypatch):
    fake_redis = FakeRedis()
    monkeypatch.setattr(services, "get_redis_client", lambda: fake_redis)
    user_model = get_user_model()
    user_model.objects.create_user(username="api_user", password="StrongPass123!")

    response = client.post(
        reverse("token-obtain-pair"),
        {"username": "api_user", "password": "StrongPass123!"},
        content_type="application/json",
    )

    assert response.status_code == 200
    assert "access" in response.json()
    assert "refresh" in response.json()
    assert "session_id" in response.json()
    assert fake_redis.values
    assert fake_redis.hashes
