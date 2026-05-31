from django.db import connections
from django.db.utils import OperationalError
from rest_framework.decorators import api_view
from rest_framework.response import Response


@api_view(["GET"])
def health_check(_request):
    return Response({"status": "ok", "service": "django-api"})


@api_view(["GET"])
def readiness_check(_request):
    try:
        connections["default"].ensure_connection()
    except OperationalError:
        return Response({"status": "error", "database": "unavailable"}, status=503)

    return Response({"status": "ok", "database": "available"})
