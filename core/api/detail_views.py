from django.shortcuts import get_object_or_404
from django.utils import timezone

from core.api.me_views import PersonalProjectionAPIView
from core.participant_selectors import (
    participant_accesses_visible_to_buyer,
    participant_journeys,
)
from operations.participant_occurrence_live import participant_occurrence_live_available
from readiness import resolve_journey_readiness
from readiness.selectors import participant_readiness_queryset
from services.models import ServiceRequirementAssessment

from .detail_projections import (
    build_access_detail,
    build_journey_detail,
    build_requirement_detail,
)


class PersonalJourneyDetailAPIView(PersonalProjectionAPIView):
    projection_code = "personal.journey.detail"

    def get(self, request, pk):
        self._guard_personal_scope(request)
        observed_at = timezone.now()
        journey = get_object_or_404(
            participant_readiness_queryset(
                request.user,
                participant_journeys(request.user),
            ).prefetch_related(
                "payment_obligations__payments",
                "commerce_orders__payments",
                "service_context__requirement_assessments__evidence",
            ),
            pk=pk,
        )
        readiness = resolve_journey_readiness(
            journey,
            viewer=request.user,
            observed_at=observed_at,
        )
        live = (
            True
            if journey.occurrence_id
            and participant_occurrence_live_available(
                occurrence=journey.occurrence,
                actor=request.user,
            )
            else None
        )
        return self._response(
            build_journey_detail(
                journey=journey,
                readiness=readiness,
                profile=request.user,
                live=live,
            ),
            observed_at=observed_at,
        )


class PersonalJourneyRequirementDetailAPIView(PersonalProjectionAPIView):
    projection_code = "personal.journey.requirement.detail"

    def get(self, request, journey_id, assessment_id):
        self._guard_personal_scope(request)
        observed_at = timezone.now()
        journey = get_object_or_404(
            participant_readiness_queryset(
                request.user,
                participant_journeys(request.user),
            ),
            pk=journey_id,
        )
        assessment = get_object_or_404(
            ServiceRequirementAssessment.objects.select_related(
                "context",
                "context__journey",
                "requirement",
            ).prefetch_related(
                "payment_obligation_links__obligation",
                "step_links__journey_step",
                "evidence",
            ),
            pk=assessment_id,
            context__journey=journey,
        )
        return self._response(
            build_requirement_detail(
                journey=journey,
                assessment=assessment,
            ),
            observed_at=observed_at,
        )


class PersonalAccessDetailAPIView(PersonalProjectionAPIView):
    projection_code = "personal.access.detail"

    def get(self, request, pk):
        self._guard_personal_scope(request)
        observed_at = timezone.now()
        access = get_object_or_404(
            participant_accesses_visible_to_buyer(request.user),
            pk=pk,
        )
        return self._response(
            build_access_detail(access=access, profile=request.user),
            observed_at=observed_at,
        )
