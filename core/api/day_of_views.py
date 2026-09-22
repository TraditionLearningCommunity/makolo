from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone

from activities.models import Occurrence
from core.api.day_of_projection import build_personal_day_of_data
from core.api.me_views import PersonalProjectionAPIView
from operations.participant_occurrence_live import resolve_participant_occurrence_live


class PersonalOccurrenceDayOfAPIView(PersonalProjectionAPIView):
    projection_code = "personal.occurrence.day_of"

    def get(self, request, pk):
        self._guard_personal_scope(request)
        observed_at = timezone.now()
        occurrence = get_object_or_404(
            Occurrence.objects.select_related("activity").prefetch_related(
                "place_links__place"
            ),
            pk=pk,
        )
        live_payload = resolve_participant_occurrence_live(
            occurrence=occurrence,
            actor=request.user,
            observed_at=observed_at,
        )
        if live_payload is None:
            raise Http404

        response = self._response(
            build_personal_day_of_data(
                profile=request.user,
                occurrence=occurrence,
                live_payload=live_payload,
            ),
            observed_at=observed_at,
        )
        response["Cache-Control"] = "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"
        return response
