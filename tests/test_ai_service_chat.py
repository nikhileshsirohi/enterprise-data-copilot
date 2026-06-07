import pytest
from django.contrib.auth import get_user_model
from django.db import connections
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
    with TestClient(app) as client:
        response = client.get("/api/v1/chat/sessions")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert len(body["sessions"]) == 1
    assert body["sessions"][0]["session_id"] == "chat_user_owned"
    assert body["sessions"][0]["user_id"] == user.id
    assert body["sessions"][0]["username"] == user.username
    assert body["sessions"][0]["title"] == "Available stock"
    assert body["sessions"][0]["message_count"] == 2
    connections.close_all()


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
    with TestClient(app) as client:
        response = client.get("/api/v1/chat/sessions/chat_detail")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["session_id"] == "chat_detail"
    assert body["user_id"] == user.id
    assert body["username"] == user.username
    assert body["title"] == "Committed quantity"
    assert [message["id"] for message in body["messages"]] == [
        user_message.id,
        assistant_message.id,
    ]
    assert body["messages"][0]["role"] == "USER"
    assert body["messages"][0]["metadata"] == {"limit": 5}
    assert body["messages"][1]["content"] == "PO1001 has committed quantity 4,983."
    connections.close_all()


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
    with TestClient(app) as client:
        response = client.get("/api/v1/chat/sessions/chat_private")

    app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json()["detail"] == "Chat session was not found."
    connections.close_all()


@pytest.mark.django_db(transaction=True)
def test_django_staff_without_superuser_flag_cannot_review_other_sessions() -> None:
    owner = get_user_model().objects.create_user(username="staff-scope-owner")
    staff_user = get_user_model().objects.create_user(
        username="staff-not-superuser",
        is_staff=True,
    )
    ChatSession.objects.create(
        session_id="staff_should_not_see",
        user=owner,
        title="Owner session",
    )

    app.dependency_overrides[require_authenticated_user] = lambda: AuthenticatedUser(
        user_id=staff_user.id,
        username=staff_user.username,
        is_staff=True,
        is_superuser=False,
    )
    with TestClient(app) as client:
        list_response = client.get("/api/v1/chat/sessions")
        detail_response = client.get("/api/v1/chat/sessions/staff_should_not_see")

    app.dependency_overrides.clear()

    assert list_response.status_code == 200
    assert list_response.json()["sessions"] == []
    assert detail_response.status_code == 404
    connections.close_all()


@pytest.mark.django_db(transaction=True)
def test_superuser_chat_sessions_endpoint_lists_all_active_sessions() -> None:
    super_user = get_user_model().objects.create_superuser(
        username="session-reviewer",
        password="StrongPass123!",
    )
    owner = get_user_model().objects.create_user(username="session-owner")
    other_owner = get_user_model().objects.create_user(username="session-other-owner")
    owner_session = ChatSession.objects.create(
        session_id="owner_visible_to_staff",
        user=owner,
        title="Owner session",
    )
    ChatMessage.objects.create(session=owner_session, role=ChatMessage.Role.USER, content="Question")
    ChatSession.objects.create(
        session_id="other_visible_to_staff",
        user=other_owner,
        title="Other session",
    )
    ChatSession.objects.create(
        session_id="inactive_hidden_from_staff",
        user=owner,
        title="Inactive session",
        is_active=False,
    )

    app.dependency_overrides[require_authenticated_user] = lambda: AuthenticatedUser(
        user_id=super_user.id,
        username=super_user.username,
        is_staff=True,
        is_superuser=True,
    )
    with TestClient(app) as client:
        response = client.get("/api/v1/chat/sessions")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    sessions = response.json()["sessions"]
    assert {session["session_id"] for session in sessions} == {
        "owner_visible_to_staff",
        "other_visible_to_staff",
    }
    assert {session["username"] for session in sessions} == {
        owner.username,
        other_owner.username,
    }
    connections.close_all()


@pytest.mark.django_db(transaction=True)
def test_superuser_chat_session_detail_endpoint_can_review_other_user_session() -> None:
    super_user = get_user_model().objects.create_superuser(
        username="detail-reviewer",
        password="StrongPass123!",
    )
    owner = get_user_model().objects.create_user(username="detail-owner")
    session = ChatSession.objects.create(
        session_id="detail_visible_to_staff",
        user=owner,
        title="Reviewable session",
    )
    ChatMessage.objects.create(
        session=session,
        role=ChatMessage.Role.ASSISTANT,
        content="Reviewed answer",
    )

    app.dependency_overrides[require_authenticated_user] = lambda: AuthenticatedUser(
        user_id=super_user.id,
        username=super_user.username,
        is_staff=True,
        is_superuser=True,
    )
    with TestClient(app) as client:
        response = client.get("/api/v1/chat/sessions/detail_visible_to_staff")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["session_id"] == "detail_visible_to_staff"
    assert body["user_id"] == owner.id
    assert body["username"] == owner.username
    assert body["messages"][0]["content"] == "Reviewed answer"
    connections.close_all()


@pytest.mark.django_db(transaction=True)
def test_chat_session_archive_endpoint_soft_deletes_owned_session() -> None:
    user = get_user_model().objects.create_user(username="chat-archive-user")
    ChatSession.objects.create(
        session_id="chat_archive",
        user=user,
        title="Archive me",
    )

    app.dependency_overrides[require_authenticated_user] = lambda: AuthenticatedUser(
        user_id=user.id,
        username=user.username,
        is_staff=False,
    )
    with TestClient(app) as client:
        response = client.delete("/api/v1/chat/sessions/chat_archive")
        list_response = client.get("/api/v1/chat/sessions")
        detail_response = client.get("/api/v1/chat/sessions/chat_archive")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "session_id": "chat_archive",
        "archived": True,
        "is_active": False,
    }
    assert ChatSession.objects.get(session_id="chat_archive").is_active is False
    assert list_response.status_code == 200
    assert list_response.json()["sessions"] == []
    assert detail_response.status_code == 404
    connections.close_all()


@pytest.mark.django_db(transaction=True)
def test_chat_session_archive_endpoint_blocks_other_users() -> None:
    owner = get_user_model().objects.create_user(username="archive-owner")
    other_user = get_user_model().objects.create_user(username="archive-intruder")
    ChatSession.objects.create(
        session_id="chat_archive_private",
        user=owner,
        title="Private archive",
    )

    app.dependency_overrides[require_authenticated_user] = lambda: AuthenticatedUser(
        user_id=other_user.id,
        username=other_user.username,
        is_staff=False,
    )
    with TestClient(app) as client:
        response = client.delete("/api/v1/chat/sessions/chat_archive_private")

    app.dependency_overrides.clear()

    assert response.status_code == 404
    assert ChatSession.objects.get(session_id="chat_archive_private").is_active is True
    connections.close_all()


@pytest.mark.django_db(transaction=True)
def test_chat_session_rename_endpoint_updates_owned_session_title() -> None:
    user = get_user_model().objects.create_user(username="chat-rename-user")
    ChatSession.objects.create(
        session_id="chat_rename",
        user=user,
        title="Old title",
    )

    app.dependency_overrides[require_authenticated_user] = lambda: AuthenticatedUser(
        user_id=user.id,
        username=user.username,
        is_staff=False,
    )
    with TestClient(app) as client:
        response = client.patch(
            "/api/v1/chat/sessions/chat_rename/title",
            json={"title": "  Inventory questions  "},
        )
        detail_response = client.get("/api/v1/chat/sessions/chat_rename")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "session_id": "chat_rename",
        "title": "Inventory questions",
    }
    assert ChatSession.objects.get(session_id="chat_rename").title == "Inventory questions"
    assert detail_response.status_code == 200
    assert detail_response.json()["title"] == "Inventory questions"
    connections.close_all()


@pytest.mark.django_db(transaction=True)
def test_chat_session_rename_endpoint_blocks_other_users() -> None:
    owner = get_user_model().objects.create_user(username="rename-owner")
    other_user = get_user_model().objects.create_user(username="rename-intruder")
    ChatSession.objects.create(
        session_id="chat_rename_private",
        user=owner,
        title="Private title",
    )

    app.dependency_overrides[require_authenticated_user] = lambda: AuthenticatedUser(
        user_id=other_user.id,
        username=other_user.username,
        is_staff=False,
    )
    with TestClient(app) as client:
        response = client.patch(
            "/api/v1/chat/sessions/chat_rename_private/title",
            json={"title": "Not allowed"},
        )

    app.dependency_overrides.clear()

    assert response.status_code == 404
    assert ChatSession.objects.get(session_id="chat_rename_private").title == "Private title"
    connections.close_all()
