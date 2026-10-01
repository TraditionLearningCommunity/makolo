from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from activities.models import Occurrence
from core.api.projections import projection_envelope

from .space_day_of import build_space_operator_day_of


class SpaceOccurrenceDayOfAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, occurrence_id):
        observed_at = timezone.now()
        occurrence = get_object_or_404(
            Occurrence.objects.select_related("activity", "activity__space"),
            pk=occurrence_id,
        )
        payload = build_space_operator_day_of(
            occurrence=occurrence,
            actor=request.user,
            observed_at=observed_at,
        )
        if payload is None:
            from rest_framework.exceptions import NotFound
            raise NotFound()

        response = Response(
            projection_envelope(
                projection="space.occurrence.day_of",
                data=payload,
                generated_at=observed_at,
                scope="space",
            )
        )
        response["Cache-Control"] = "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"
        return response
