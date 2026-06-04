from types import SimpleNamespace

from backend.ai_service.services import intent_router
from backend.ai_service.services.intent_router import IntentRouter


class FakeEmbeddingClient:
    def __init__(
        self,
        embeddings: dict[str, list[float]] | None = None,
        default_embedding: list[float] | None = None,
    ) -> None:
        self.embeddings = embeddings or {}
        self.default_embedding = default_embedding or [0.0, 0.0, 1.0]

    def embed(self, model: str, text: str):
        return self.embeddings.get(text, self.default_embedding)


class FakeLLMClient:
    def generate(self, model: str, prompt: str) -> str:
        assert model
        assert "Classify this user question" in prompt
        return '{"intent":"policy","confidence":0.74,"reason":"mentions employee guideline"}'


def test_intent_router_routes_policy_questions_to_policy_rag() -> None:
    decision = IntentRouter(embedding_client=FakeEmbeddingClient()).decide(
        "What is the reimbursement limit for meals?"
    )

    assert decision.intent == "policy"
    assert decision.confidence == 0.90
    assert "Stage 2 keyword" in decision.reason


def test_intent_router_routes_business_entity_questions_to_database() -> None:
    decision = IntentRouter(embedding_client=FakeEmbeddingClient()).decide(
        "Available stock of material MAT0006"
    )

    assert decision.intent == "database"
    assert decision.confidence == 0.95
    assert "Stage 1 entity rule" in decision.reason


def test_intent_router_uses_embedding_similarity_when_keywords_are_unclear() -> None:
    embeddings = {
        "Can I submit dinner costs after a client visit?": [1.0, 0.0, 0.0],
        "What is the reimbursement limit for meals?": [1.0, 0.0, 0.0],
    }

    decision = IntentRouter(embedding_client=FakeEmbeddingClient(embeddings)).decide(
        "Can I submit dinner costs after a client visit?"
    )

    assert decision.intent == "policy"
    assert decision.confidence == 1.0
    assert "Stage 3 embedding similarity" in decision.reason


def test_intent_router_uses_llm_fallback_when_rules_and_embeddings_are_uncertain(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        intent_router,
        "get_settings",
        lambda: SimpleNamespace(
            ollama_embedding_model="nomic-embed-text",
            intent_embedding_confidence_threshold=0.78,
            intent_llm_fallback_enabled=True,
        ),
    )

    decision = IntentRouter(
        embedding_client=FakeEmbeddingClient(
            {"Tell me about employee guidelines": [0.1, 0.2, 0.3]},
            default_embedding=[0.0, 0.0, 0.0],
        ),
        llm_client=FakeLLMClient(),
    ).decide("Tell me about employee guidelines")

    assert decision.intent == "policy"
    assert decision.confidence == 0.74
    assert "Stage 4 LLM fallback" in decision.reason


def test_intent_router_defaults_unclear_questions_to_database_when_fallback_fails() -> None:
    class FailingLLMClient:
        def generate(self, model: str, prompt: str) -> str:
            return "not-json"

    decision = IntentRouter(
        embedding_client=FakeEmbeddingClient(
            {"show recent activity": [0.1, 0.2, 0.3]},
            default_embedding=[0.0, 0.0, 0.0],
        ),
        llm_client=FailingLLMClient(),
    ).decide("show recent activity")

    assert decision.intent == "database"
    assert decision.confidence == 0.55
