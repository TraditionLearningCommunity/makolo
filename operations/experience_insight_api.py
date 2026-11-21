from django.shortcuts import get_object_or_404

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import NotFound
from uuid import UUID

from activities.models import Occurrence
from authorization.services import effective_permission_codes
from organizations.models import Organization
from .experience_insights import resolve_occurrence_insight


class OccurrenceExperienceInsightAPIView(APIView):
    """Rechecks owner mandate for every read. Never caches private summaries."""
    permission_classes = [IsAuthenticated]

    def get(self, request, occurrence_id, kind):
        occurrence = get_object_or_404(
            Occurrence.objects.select_related("activity", "activity__space"),
            pk=occurrence_id,
        )
        actor_space = request.query_params.get("actor_space")
        if actor_space:
            try:
                selected = Organization.objects.filter(pk=UUID(actor_space)).first()
            except (ValueError, TypeError, AttributeError):
                raise NotFound()
            if selected is None or selected.pk != occurrence.activity.space_id:
                raise NotFound()
            if not (
                effective_permission_codes(
                    request.user, space=selected, include_platform=False,
                ) or effective_permission_codes(
                    request.user, activity=occurrence.activity, include_platform=False,
                )
            ):
                raise NotFound()

        payload = resolve_occurrence_insight(
            occurrence=occurrence,
            viewer=request.user,
            kind=kind,
            organizer_scope=not actor_space or occurrence.activity.space_id == selected.pk,
        )
        if payload is None:
            raise NotFound()
        response = Response({
            "identity": {"kind": "occurrence", "id": str(occurrence.pk)},
            "data": payload,
        })
        response["Cache-Control"] = "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"
        return response
