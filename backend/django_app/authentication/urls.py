from django.urls import path

from backend.django_app.authentication.views import LoginView, LogoutView, MeView, RefreshView

urlpatterns = [
    path("login/", LoginView.as_view(), name="token-obtain-pair"),
    path("refresh/", RefreshView.as_view(), name="token-refresh"),
    path("logout/", LogoutView.as_view(), name="token-logout"),
    path("me/", MeView.as_view(), name="auth-me"),
]
