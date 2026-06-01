from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        return Response({
            "_id": user.id,
            "username": user.username,
            "email": user.email,
            "is_staff": user.is_staff,
        })