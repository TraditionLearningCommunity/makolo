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
        actor_space_id = request.query_params.get("actor_space")
        if actor_space_id:
            from uuid import UUID
            try:
                actor_space_id = UUID(actor_space_id)
            except (ValueError, TypeError, AttributeError):
                raise NotFound()
        data = resolve_occurrence_experience(
            occurrence=occurrence,
            viewer=request.user,
            surface=self.surface,
            observed_at=now,
            actor_space_id=actor_space_id,
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

class OccurrenceExperienceLiveConfigurationAPIView(APIView):
    """Owner-only Live opt-in. Viewer authority never comes from a UI mode."""
    permission_classes = [IsAuthenticated]

    def post(self, request, occurrence_id):
        from rest_framework.exceptions import ValidationError
        from activities.services import set_occurrence_live_enabled

        enabled = request.data.get("enabled")
        if not isinstance(enabled, bool):
            raise ValidationError({"enabled": "Un booléen est obligatoire."})
        occurrence = get_object_or_404(
            Occurrence.objects.select_related("activity", "activity__space"),
            pk=occurrence_id,
        )
        updated = set_occurrence_live_enabled(
            occurrence=occurrence, actor=request.user, enabled=enabled,
        )
        response = Response({
            "occurrence_id": str(updated.pk),
            "live_enabled": updated.live_enabled,
        })
        response["Cache-Control"] = "private, no-store"
        return response
