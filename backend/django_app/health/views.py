from django.db import connections
from django.db.utils import OperationalError
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny


@api_view(["GET"])
@permission_classes([AllowAny])
def root(_request):
    return Response(
        {
            "service": "enterprise-data-copilot-django-api",
            "status": "ok",
            "version": "v1",
            "endpoints": {
                "health": "/api/v1/health/",
                "readiness": "/api/v1/health/ready/",
                "ai_metadata_search": "http://127.0.0.1:8001/api/v1/metadata/search",
            },
        }
    )


@api_view(["GET"])
@permission_classes([AllowAny])
def health_check(_request):
    return Response({"status": "ok", "service": "django-api"})


@api_view(["GET"])
@permission_classes([AllowAny])
def readiness_check(_request):
    try:
        connections["default"].ensure_connection()
    except OperationalError:
        return Response({"status": "error", "database": "unavailable"}, status=503)

    return Response({"status": "ok", "database": "available"})
