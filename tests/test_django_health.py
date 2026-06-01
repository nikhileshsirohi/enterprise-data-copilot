import pytest
from django.urls import reverse


def test_root_endpoint_returns_service_info(client):
    response = client.get(reverse("root"))

    assert response.status_code == 200
    assert response.json()["service"] == "enterprise-data-copilot-django-api"


@pytest.mark.django_db
def test_health_endpoint_returns_ok(client):
    response = client.get(reverse("health-check"))

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "django-api"}
