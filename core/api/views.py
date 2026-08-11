from django.db import DatabaseError, connection

from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView


class HealthAPIView(APIView):
    """Liveness only: proves the Django process can answer HTTP."""

    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        return Response({"status": "ok", "api_version": "v1"})


class ReadinessAPIView(APIView):
    """Readiness: performs one minimal query against the configured database."""

    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
        except DatabaseError:
            return Response(
                {"status": "unavailable"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response({"status": "ready"})
