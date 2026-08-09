from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView


class HealthAPIView(APIView):
    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        return Response({"status": "ok", "api_version": "v1"})
