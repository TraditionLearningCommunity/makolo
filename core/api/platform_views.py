from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.platform_presentation import platform_modules_for


class PlatformCapabilitiesAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        modules = platform_modules_for(request.user)
        if not modules:
            raise PermissionDenied("Autorité Platform requise.")
        response = Response({
            "context": "platform",
            "modules": modules,
            "space_modules_included": False,
            "personal_modules_included": False,
        })
        response["Cache-Control"] = "private, no-store"
        return response
