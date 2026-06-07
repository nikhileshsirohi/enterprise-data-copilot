from backend.ai_service.api.v1.routes import ask as ask_route
from backend.ai_service.schemas.ask import AskRequest, AskResponse
from backend.ai_service.security.jwt_auth import AuthenticatedUser
from backend.ai_service.services.chat_history import ChatContextMessage
from backend.ai_service.services.intent_router import IntentDecision
from backend.ai_service.services.semantic_cache import SemanticCacheHit


def build_response(*, cache_hit: bool = False) -> AskResponse:
    return AskResponse(
        question="committed quantity of PO1001",
        answer="PO1001 has committed quantity 4983.",
        answer_source="database",
        sql="SELECT 1",
        is_sql_valid=True,
        validation_reason=None,
        columns=["value"],
        rows=[{"value": 1}],
        row_count=1,
        truncated=False,
        metadata=[],
        cache_hit=cache_hit,
        cache_similarity=1.0 if cache_hit else None,
    )


class FakeIntentRouter:
    def decide(self, question: str) -> IntentDecision:
        return IntentDecision(
            intent="database",
            confidence=0.95,
            reason="test database intent",
        )


class FakeChatHistoryReader:
    def get_recent_context(self, *, session_id, user_id, limit):
        assert session_id == "chat_existing"
        return [ChatContextMessage(role="USER", content="committed quantity of PO1001")]


class FakeAuditLogger:
    def record(self, record):
        self.record = record


def test_ask_uses_semantic_cache_even_when_frontend_session_has_context(monkeypatch):
    class FakeSemanticCache:
        def get(self, question: str):
            return SemanticCacheHit(
                key="semantic_cache:ask:test",
                similarity=1.0,
                response=build_response(cache_hit=True),
            )

        def set(self, question: str, response: AskResponse):
            raise AssertionError("Cache hits should not write a new cache entry.")

    class FailingQuestionAnswerer:
        def __init__(self, *args, **kwargs):
            raise AssertionError("LLM-backed database answerer should not run on cache hit.")

    monkeypatch.setattr(ask_route, "ChatHistoryReader", lambda: FakeChatHistoryReader())
    monkeypatch.setattr(ask_route, "IntentRouter", lambda: FakeIntentRouter())
    monkeypatch.setattr(ask_route, "SemanticCache", lambda: FakeSemanticCache())
    monkeypatch.setattr(ask_route, "QuestionAnswerer", FailingQuestionAnswerer)
    monkeypatch.setattr(ask_route, "AskAuditLogger", lambda: FakeAuditLogger())

    response = ask_route.ask_question(
        AskRequest(
            question="committed quantity of PO1001",
            session_id="chat_existing",
            persist=False,
            use_cache=True,
        ),
        current_user=AuthenticatedUser(
            user_id=1,
            username="frontend-user",
            is_staff=False,
        ),
    )

    assert response.cache_hit is True
    assert response.used_chat_context is True
    assert response.chat_context_message_count == 1


def test_ask_does_not_store_contextual_cache_misses(monkeypatch):
    class FakeSemanticCache:
        def __init__(self):
            self.set_called = False

        def get(self, question: str):
            return None

        def set(self, question: str, response: AskResponse):
            self.set_called = True
            raise AssertionError("Contextual answers must not be stored in semantic cache.")

    class FakeQuestionAnswerer:
        def __init__(self, *args, **kwargs):
            pass

        def ask(self, *, question, limit, chat_context, user_id):
            assert chat_context
            return build_response()

    monkeypatch.setattr(ask_route, "ChatHistoryReader", lambda: FakeChatHistoryReader())
    monkeypatch.setattr(ask_route, "IntentRouter", lambda: FakeIntentRouter())
    monkeypatch.setattr(ask_route, "SemanticCache", lambda: FakeSemanticCache())
    monkeypatch.setattr(ask_route, "SQLGenerator", lambda metadata_retriever: object())
    monkeypatch.setattr(ask_route, "get_metadata_retriever", lambda: object())
    monkeypatch.setattr(ask_route, "QuestionAnswerer", FakeQuestionAnswerer)
    monkeypatch.setattr(ask_route, "AskAuditLogger", lambda: FakeAuditLogger())

    response = ask_route.ask_question(
        AskRequest(
            question="committed quantity of PO1001",
            session_id="chat_existing",
            persist=False,
            use_cache=True,
        ),
        current_user=AuthenticatedUser(
            user_id=1,
            username="frontend-user",
            is_staff=False,
        ),
    )

    assert response.cache_hit is False
    assert response.used_chat_context is True
    assert response.chat_context_message_count == 1
