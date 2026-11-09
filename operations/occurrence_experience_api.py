"""Additive canonical Jour J and Live projections for cumulative authority."""
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from activities.models import Occurrence
from core.api.projections import projection_envelope
from .occurrence_experience import resolve_occurrence_experience


class _OccurrenceExperienceAPIView(APIView):
    permission_classes = [IsAuthenticated]
    surface = None

    def get(self, request, occurrence_id):
        from rest_framework.exceptions import NotFound

        now = timezone.now()
        occurrence = get_object_or_404(
            Occurrence.objects.select_related("activity", "activity__space")
            .prefetch_related("place_links__place"),
            pk=occurrence_id,
        )
        data = resolve_occurrence_experience(
            occurrence=occurrence,
            viewer=request.user,
            surface=self.surface,
            observed_at=now,
        )
        if data is None:
            raise NotFound()
        response = Response(projection_envelope(
            projection=f"occurrence.experience.{self.surface}",
            data=data,
            generated_at=now,
            scope="occurrence",
        ))
        response["Cache-Control"] = "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"
        return response


class OccurrenceExperienceDayOfAPIView(_OccurrenceExperienceAPIView):
    surface = "day_of"


class OccurrenceExperienceLiveAPIView(_OccurrenceExperienceAPIView):
    surface = "live"
