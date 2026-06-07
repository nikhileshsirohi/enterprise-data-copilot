from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from backend.django_app.authentication.services import (
    is_refresh_token_active,
    revoke_login_session,
    track_login_session,
)


class LoginView(TokenObtainPairView):
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code != status.HTTP_200_OK:
            return response

        access = AccessToken(response.data["access"])
        session_id = track_login_session(
            user_id=int(access["user_id"]),
            username=request.data.get("username", ""),
            refresh_token=response.data["refresh"],
        )
        response.data["session_id"] = session_id
        response.data["token_type"] = "Bearer"
        return response


class RefreshView(TokenRefreshView):
    def post(self, request, *args, **kwargs):
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            return Response({"detail": "Refresh token is required."}, status=400)

        try:
            if not is_refresh_token_active(refresh_token):
                return Response({"detail": "Refresh token has been revoked."}, status=401)
        except TokenError:
            return Response({"detail": "Invalid refresh token."}, status=401)

        return super().post(request, *args, **kwargs)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            revoke_login_session(
                refresh_token=request.data.get("refresh"),
                session_id=request.data.get("session_id"),
            )
        except TokenError:
            return Response({"detail": "Invalid refresh token."}, status=400)

        return Response(status=204)


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        return Response(
            {
                "_id": user.id,
                "username": user.username,
                "email": user.email,
                "is_staff": user.is_staff,
                "is_superuser": user.is_superuser,
            }
        )
