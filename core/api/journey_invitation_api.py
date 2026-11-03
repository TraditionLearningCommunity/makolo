"""Native beneficiary actions for an existing Journey invitation.

The canonical Journey transition and Access issuance are shared with Web.
"""
from django.core.exceptions import ValidationError as DomainValidationError
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.participant_actions import participant_accept_invitation, participant_decline_invitation
from journeys.models import Journey, JourneyStatus, WorkflowKind


class PersonalJourneyInvitationAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def _journey(self, request, pk):
        return get_object_or_404(
            Journey.objects.filter(
                beneficiary=request.user,
                workflow=WorkflowKind.INVITATION,
            ).select_related("activity", "occurrence"),
            pk=pk,
        )

    def _response(self, journey, *, access=None):
        can_respond = journey.status == JourneyStatus.SUBMITTED
        payload = {
            "kind": "journey_invitation",
            "journey_id": str(journey.pk),
            "status": journey.status,
            "capabilities": ["accept", "decline"] if can_respond else [],
            "access_id": str(access.pk) if access is not None else None,
        }
        response = Response(payload)
        response["Cache-Control"] = "private, no-store"
        return response

    def get(self, request, pk):
        journey = self._journey(request, pk)
        return self._response(journey)

    def post(self, request, pk):
        journey = self._journey(request, pk)
        if not isinstance(request.data, dict) or set(request.data) != {"decision"}:
            raise ValidationError({"decision": "Indiquez une décision valide."})
        decision = request.data["decision"]
        if decision not in {"accept", "decline"}:
            raise ValidationError({"decision": "Décision inconnue."})
        # Repeated requests cannot turn an accepted invitation into a refusal.
        if decision == "accept" and journey.status == JourneyStatus.CANCELLED:
            raise ValidationError({"decision": "Cette invitation a été refusée."})
        if decision == "decline" and journey.status == JourneyStatus.CONFIRMED:
            raise ValidationError({"decision": "Cette invitation est déjà acceptée."})
        try:
            if decision == "accept":
                journey, access = participant_accept_invitation(
                    journey=journey, actor=request.user,
                )
                return self._response(journey, access=access)
            journey = participant_decline_invitation(journey=journey, actor=request.user)
            return self._response(journey)
        except DomainValidationError as exc:
            raise ValidationError({"decision": exc.messages}) from exc
