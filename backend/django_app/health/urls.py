from django.urls import path

from backend.django_app.health.views import health_check, readiness_check

urlpatterns = [
    path("", health_check, name="health-check"),
    path("ready/", readiness_check, name="readiness-check"),
]
