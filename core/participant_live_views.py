from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.generic import TemplateView

from activities.models import Occurrence
from journeys.models import JourneyStatus
from operations.participant_live import resolve_participant_occurrence_live

from .participant_action_presentation import occurrence_live_presentation
from .participant_presentation import occurrence_timing
from .participant_selectors import participant_journeys


class ParticipantOccurrenceLiveView(LoginRequiredMixin, TemplateView):
    """Personal Occurrence Live surface with an explicit participant perspective.

    A Profile may simultaneously hold operator authority. `/me/` must still
    expose only their participant facts and actions, never operator payloads.
    """

    template_name = "core/participant_occurrence_live.html"
    login_url = "core:login"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        occurrence = get_object_or_404(
            Occurrence.objects.select_related("activity").prefetch_related("place_links__place"),
            pk=kwargs["pk"],
        )
        payload = resolve_participant_occurrence_live(
            occurrence=occurrence,
            actor=self.request.user,
        )
        if payload is None:
            raise Http404

        journey = (
            participant_journeys(self.request.user)
            .filter(occurrence=occurrence)
            .exclude(status__in={JourneyStatus.REJECTED, JourneyStatus.CANCELLED, JourneyStatus.EXPIRED})
            .order_by("created_at", "id")
            .first()
        )
        access_id = next((row["id"] for row in payload["access"] if row["usable"]), None)
        if access_id is None and payload["access"]:
            access_id = payload["access"][0]["id"]

        context.update(
            {
                "occurrence": occurrence,
                "journey": journey,
                "live": payload,
                "live_ui": occurrence_live_presentation(
                    payload=payload,
                    timing=occurrence_timing(occurrence),
                ),
                "journey_url": reverse("core:participant-journey-detail", kwargs={"pk": journey.pk}) if journey else None,
                "access_url": reverse("core:participant-access-detail", kwargs={"pk": access_id}) if access_id else None,
            }
        )
        return context
