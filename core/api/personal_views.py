from django.utils import timezone

from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from core.api.personal_projections import (
    build_personal_now_projection,
    build_personal_ongoing_projection,
)
from core.api.projections import projection_envelope


class PersonalNowAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        observed_at = timezone.now()
        data = build_personal_now_projection(request.user, observed_at=observed_at)
        return Response(
            projection_envelope(
                projection="personal.now",
                data=data,
                generated_at=observed_at,
            )
        )


class PersonalOngoingAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        observed_at = timezone.now()
        data = build_personal_ongoing_projection(request.user, observed_at=observed_at)
        return Response(
            projection_envelope(
                projection="personal.ongoing",
                data=data,
                generated_at=observed_at,
            )
        )
