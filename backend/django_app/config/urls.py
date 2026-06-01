from django.urls import include, path

from backend.django_app.health.views import root

urlpatterns = [
    path("", root, name="root"),
    path("api/v1/health/", include("backend.django_app.health.urls")),
    path("api/v1/auth/", include("backend.django_app.authentication.urls")),
]
