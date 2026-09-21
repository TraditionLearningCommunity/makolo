from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.participant_selectors import (
    participant_accesses_visible_to_buyer,
    participant_journeys,
)
from operations.participant_occurrence_live import resolve_participant_occurrence_live
from readiness import resolve_journey_readiness
from readiness.selectors import participant_readiness_queryset
from services.models import ServiceRequirementAssessment

from .detail_projections import (
    build_access_detail,
    build_journey_detail,
    build_requirement_detail,
)
from .projections import projection_envelope


class PersonalJourneyDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        observed_at = timezone.now()
        journey = get_object_or_404(
            participant_readiness_queryset(
                request.user,
                participant_journeys(request.user),
            ).prefetch_related(
                "payment_obligations__payments",
                "commerce_orders__payments",
            ),
            pk=pk,
        )
        readiness = resolve_journey_readiness(
            journey,
            viewer=request.user,
            observed_at=observed_at,
        )
        live = (
            resolve_participant_occurrence_live(
                occurrence=journey.occurrence,
                actor=request.user,
                observed_at=observed_at,
            )
            if journey.occurrence_id
            else None
        )
        return Response(
            projection_envelope(
                projection="personal.journey.detail",
                data=build_journey_detail(
                    journey=journey,
                    readiness=readiness,
                    profile=request.user,
                    live=live,
                ),
                generated_at=observed_at,
            )
        )


class PersonalJourneyRequirementDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, journey_id, assessment_id):
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
        return Response(
            projection_envelope(
                projection="personal.journey.requirement.detail",
                data=build_requirement_detail(
                    journey=journey,
                    assessment=assessment,
                ),
                generated_at=observed_at,
            )
        )


class PersonalAccessDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        observed_at = timezone.now()
        access = get_object_or_404(
            participant_accesses_visible_to_buyer(request.user),
            pk=pk,
        )
        return Response(
            projection_envelope(
                projection="personal.access.detail",
                data=build_access_detail(access=access, profile=request.user),
                generated_at=observed_at,
            )
        )
