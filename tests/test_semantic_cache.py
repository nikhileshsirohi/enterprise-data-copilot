from backend.ai_service.schemas.ask import AskResponse
from backend.ai_service.services.semantic_cache import SemanticCache


class FakeRedis:
    def __init__(self) -> None:
        self.values = {}

    def scan_iter(self, pattern):
        return list(self.values.keys())

    def get(self, key):
        return self.values.get(key)

    def set(self, key, value, ex=None):
        self.values[key] = value


class FakeEmbeddingClient:
    def __init__(self, embedding):
        self.embedding = embedding

    def embed(self, model: str, text: str):
        return self.embedding


def build_response() -> AskResponse:
    return AskResponse(
        question="committed quantity of PO1001",
        answer="PO1001 has committed quantity 4983.",
        sql="SELECT 1",
        is_sql_valid=True,
        validation_reason=None,
        columns=["value"],
        rows=[{"value": 1}],
        row_count=1,
        truncated=False,
        metadata=[],
    )


def test_semantic_cache_stores_and_returns_hit() -> None:
    fake_redis = FakeRedis()
    cache = SemanticCache(
        redis_client=fake_redis,
        embedding_client=FakeEmbeddingClient([1.0, 0.0, 0.0]),
    )

    key = cache.set("committed quantity of PO1001", build_response())
    hit = cache.get("what is committed qty for PO1001")

    assert key is not None
    assert hit is not None
    assert hit.similarity == 1.0
    assert hit.response.cache_hit is True
    assert hit.response.answer == "PO1001 has committed quantity 4983."


def test_semantic_cache_miss_when_similarity_is_low() -> None:
    fake_redis = FakeRedis()
    writer = SemanticCache(
        redis_client=fake_redis,
        embedding_client=FakeEmbeddingClient([1.0, 0.0, 0.0]),
    )
    writer.set("committed quantity of PO1001", build_response())

    reader = SemanticCache(
        redis_client=fake_redis,
        embedding_client=FakeEmbeddingClient([0.0, 1.0, 0.0]),
    )
    hit = reader.get("unrelated question")

    assert hit is None
