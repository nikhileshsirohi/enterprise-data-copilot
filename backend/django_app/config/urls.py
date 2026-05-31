from django.urls import include, path

urlpatterns = [
    path("api/v1/health/", include("backend.django_app.health.urls")),
]
