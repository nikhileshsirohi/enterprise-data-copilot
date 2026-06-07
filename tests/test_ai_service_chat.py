import pytest
from django.contrib.auth import get_user_model
from fastapi.testclient import TestClient

from backend.ai_service.main import app
from backend.ai_service.security.jwt_auth import AuthenticatedUser, require_authenticated_user
from backend.django_app.core.models import ChatMessage, ChatSession


@pytest.mark.django_db(transaction=True)
def test_chat_sessions_endpoint_lists_current_user_sessions() -> None:
    user = get_user_model().objects.create_user(username="chat-user")
    other_user = get_user_model().objects.create_user(username="other-chat-user")
    session = ChatSession.objects.create(
        session_id="chat_user_owned",
        user=user,
        title="Available stock",
    )
    ChatMessage.objects.create(session=session, role=ChatMessage.Role.USER, content="Question")
    ChatMessage.objects.create(
        session=session,
        role=ChatMessage.Role.ASSISTANT,
        content="Answer",
    )
    ChatSession.objects.create(
        session_id="chat_other_owned",
        user=other_user,
        title="Other session",
    )

    app.dependency_overrides[require_authenticated_user] = lambda: AuthenticatedUser(
        user_id=user.id,
        username=user.username,
        is_staff=False,
    )
    client = TestClient(app)

    response = client.get("/api/v1/chat/sessions")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert len(body["sessions"]) == 1
    assert body["sessions"][0]["session_id"] == "chat_user_owned"
    assert body["sessions"][0]["title"] == "Available stock"
    assert body["sessions"][0]["message_count"] == 2


@pytest.mark.django_db(transaction=True)
def test_chat_session_detail_endpoint_returns_messages() -> None:
    user = get_user_model().objects.create_user(username="chat-detail-user")
    session = ChatSession.objects.create(
        session_id="chat_detail",
        user=user,
        title="Committed quantity",
    )
    user_message = ChatMessage.objects.create(
        session=session,
        role=ChatMessage.Role.USER,
        content="committed quantity of PO1001",
        metadata={"limit": 5},
    )
    assistant_message = ChatMessage.objects.create(
        session=session,
        role=ChatMessage.Role.ASSISTANT,
        content="PO1001 has committed quantity 4,983.",
        metadata={"row_count": 1},
    )

    app.dependency_overrides[require_authenticated_user] = lambda: AuthenticatedUser(
        user_id=user.id,
        username=user.username,
        is_staff=False,
    )
    client = TestClient(app)

    response = client.get("/api/v1/chat/sessions/chat_detail")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["session_id"] == "chat_detail"
    assert body["title"] == "Committed quantity"
    assert [message["id"] for message in body["messages"]] == [
        user_message.id,
        assistant_message.id,
    ]
    assert body["messages"][0]["role"] == "USER"
    assert body["messages"][0]["metadata"] == {"limit": 5}
    assert body["messages"][1]["content"] == "PO1001 has committed quantity 4,983."


@pytest.mark.django_db(transaction=True)
def test_chat_session_detail_endpoint_blocks_other_users() -> None:
    owner = get_user_model().objects.create_user(username="chat-owner")
    other_user = get_user_model().objects.create_user(username="chat-intruder")
    ChatSession.objects.create(
        session_id="chat_private",
        user=owner,
        title="Private session",
    )

    app.dependency_overrides[require_authenticated_user] = lambda: AuthenticatedUser(
        user_id=other_user.id,
        username=other_user.username,
        is_staff=False,
    )
    client = TestClient(app)

    response = client.get("/api/v1/chat/sessions/chat_private")

    app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json()["detail"] == "Chat session was not found."
