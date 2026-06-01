from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from backend.django_app.authentication.views import MeView

urlpatterns = [
    path("login/", TokenObtainPairView.as_view(), name="token-obtain-pair"),
    path("refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("me/", MeView.as_view(), name="auth-me"),
]