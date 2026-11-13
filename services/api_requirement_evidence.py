"""Owner-backed submission of existing JourneyArtifacts as Requirement evidence.

This creates a pending evidence relation; it never evaluates or satisfies
Readiness/Requirement. A client cannot choose beneficiary, assessor or status.
"""
from collections.abc import Mapping
from uuid import UUID

from django.core.exceptions import PermissionDenied as DomainPermissionDenied
from django.core.exceptions import ValidationError as DomainValidationError
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from journeys import collaboration_services
from journeys.models import Journey, WorkflowKind
from .models import ServiceRequirementAssessment, ServiceRequirementEvidence
from .requirement_services import submit_requirement_evidence
from .space_beneficiary_api import _journey as space_journey


class ServiceRequirementEvidenceAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def _journey(self, request, journey_id, slug):
        if slug is not None:
            return space_journey(request, slug, journey_id, write=True)[1]
        return get_object_or_404(
            Journey.objects.select_related("activity"),
            pk=journey_id, beneficiary=request.user, workflow=WorkflowKind.SERVICE,
        )

    def post(self, request, journey_id, assessment_id, slug=None):
        journey = self._journey(request, journey_id, slug)
        if not isinstance(request.data, Mapping) or set(request.data) != {"artifact_id"}:
            raise ValidationError({"artifact_id": "Choisissez une pièce de cette démarche."})
        try:
            artifact_id = UUID(str(request.data["artifact_id"]))
        except (ValueError, TypeError):
            raise ValidationError({"artifact_id": "Identifiant de pièce invalide."}) from None
        assessment = (
            ServiceRequirementAssessment.objects.select_related(
                "context", "context__journey", "requirement",
            )
            .filter(pk=assessment_id, context__journey=journey)
            .first()
        )
        if assessment is None:
            raise NotFound()
        artifact = (
            collaboration_services.artifacts_for_actor(
                actor=request.user, journey=journey,
            )
            .filter(pk=artifact_id)
            .first()
        )
        if artifact is None:
            raise NotFound()
        try:
            evidence = submit_requirement_evidence(
                assessment=assessment, artifact=artifact, actor=request.user,
            )
        except DomainPermissionDenied:
            raise NotFound() from None
        except DomainValidationError as exc:
            raise ValidationError(
                getattr(exc, "message_dict", None) or exc.messages,
            ) from exc
        response = Response({
            "evidence": {
                "id": str(evidence.pk),
                "assessment_id": str(assessment.pk),
                "artifact_id": str(artifact.pk),
                "status": evidence.status,
            },
            "requirement": {
                "id": str(assessment.pk),
                "state": assessment.status,
            },
            "message": "La pièce a été proposée comme preuve. La condition reste évaluée par son propriétaire.",
        })
        response["Cache-Control"] = "private, no-store"
        return response
