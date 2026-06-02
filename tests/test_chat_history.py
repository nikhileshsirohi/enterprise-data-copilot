from django.contrib.auth import get_user_model

from backend.ai_service.schemas.ask import AskResponse
from backend.ai_service.services.chat_history import (
    ChatHistoryReader,
    ChatHistoryRecorder,
    ChatPersistenceError,
)
from backend.django_app.core.models import ChatMessage, ChatSession


def build_answer() -> AskResponse:
    return AskResponse(
        question="committed quantity of PO1001",
        answer="PO1001 has a committed quantity of 4,983.",
        sql="SELECT 1",
        is_sql_valid=True,
        validation_reason=None,
        columns=["value"],
        rows=[{"value": 1}],
        row_count=1,
        truncated=False,
        metadata=[],
        retry_count=0,
    )


def test_chat_history_skips_without_user_or_session() -> None:
    result = ChatHistoryRecorder().record_exchange(
        user_id=None,
        session_id=None,
        question="hello",
        answer=build_answer(),
        limit=5,
    )

    assert result.persisted is False


def test_chat_history_creates_session_and_messages(db) -> None:
    user = get_user_model().objects.create_user(username="copilot-user")

    result = ChatHistoryRecorder().record_exchange(
        user_id=user.id,
        session_id=None,
        question="committed quantity of PO1001",
        answer=build_answer(),
        limit=5,
    )

    assert result.persisted is True
    assert result.session_id is not None
    assert ChatSession.objects.filter(session_id=result.session_id, user=user).exists()
    assert ChatMessage.objects.filter(
        id=result.user_message_id,
        role=ChatMessage.Role.USER,
    ).exists()
    assistant_message = ChatMessage.objects.get(
        id=result.assistant_message_id,
        role=ChatMessage.Role.ASSISTANT,
    )
    assert assistant_message.metadata["sql"] == "SELECT 1"
    assert assistant_message.metadata["row_count"] == 1


def test_chat_history_appends_to_existing_session(db) -> None:
    user = get_user_model().objects.create_user(username="copilot-user")
    session = ChatSession.objects.create(session_id="chat_test", user=user)

    result = ChatHistoryRecorder().record_exchange(
        user_id=user.id,
        session_id=session.session_id,
        question="next question",
        answer=build_answer(),
        limit=3,
    )

    assert result.persisted is True
    assert result.session_id == "chat_test"
    assert session.messages.count() == 2


def test_chat_history_rejects_session_user_mismatch(db) -> None:
    user = get_user_model().objects.create_user(username="owner")
    other_user = get_user_model().objects.create_user(username="other")
    session = ChatSession.objects.create(session_id="chat_owner", user=user)

    try:
        ChatHistoryRecorder().record_exchange(
            user_id=other_user.id,
            session_id=session.session_id,
            question="bad",
            answer=build_answer(),
            limit=3,
        )
    except ChatPersistenceError as exc:
        assert "does not belong" in str(exc)
    else:
        raise AssertionError("Expected ChatPersistenceError")


def test_chat_history_reader_returns_recent_context_in_chronological_order(db) -> None:
    user = get_user_model().objects.create_user(username="context-user")
    session = ChatSession.objects.create(session_id="chat_context", user=user)
    ChatMessage.objects.create(session=session, role=ChatMessage.Role.USER, content="first")
    ChatMessage.objects.create(session=session, role=ChatMessage.Role.ASSISTANT, content="second")
    ChatMessage.objects.create(session=session, role=ChatMessage.Role.USER, content="third")

    context = ChatHistoryReader().get_recent_context(
        session_id=session.session_id,
        user_id=user.id,
        limit=2,
    )

    assert [message.content for message in context] == ["second", "third"]
    assert [message.role for message in context] == [
        ChatMessage.Role.ASSISTANT,
        ChatMessage.Role.USER,
    ]


def test_chat_history_reader_rejects_session_user_mismatch(db) -> None:
    user = get_user_model().objects.create_user(username="context-owner")
    other_user = get_user_model().objects.create_user(username="context-other")
    session = ChatSession.objects.create(session_id="chat_context_owner", user=user)

    try:
        ChatHistoryReader().get_recent_context(
            session_id=session.session_id,
            user_id=other_user.id,
            limit=2,
        )
    except ChatPersistenceError as exc:
        assert "does not belong" in str(exc)
    else:
        raise AssertionError("Expected ChatPersistenceError")
