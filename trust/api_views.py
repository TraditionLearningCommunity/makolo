from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.status import HTTP_400_BAD_REQUEST, HTTP_403_FORBIDDEN
from rest_framework.views import APIView

from journeys.models import Journey
from organizations.models import Organization

from .models import Dispute, Report
from .selectors import dispute_visible_to, get_public_trust_summary, proofs_for_profile, public_proof_by_id
from .services import create_report, submit_feedback


def _error_response(exc):
    status = HTTP_403_FORBIDDEN if isinstance(exc, PermissionDenied) else HTTP_400_BAD_REQUEST
    if hasattr(exc, "message_dict"):
        detail = exc.message_dict
    else:
        detail = getattr(exc, "messages", [str(exc)])
    return Response({"detail": detail}, status=status)


def _proof_payload(proof):
    return {
        "public_id": str(proof.public_id),
        "proof_type": proof.proof_type,
        "status": proof.status,
        "is_public": proof.is_public,
        "issued_at": proof.issued_at,
        "revoked_at": proof.revoked_at,
        "activity": {"id": str(proof.journey.activity_id), "title": proof.journey.activity.title},
        "occurrence_id": str(proof.occurrence_id) if proof.occurrence_id else None,
    }


class PublicSpaceTrustAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, space_id):
        space = get_object_or_404(Organization, pk=space_id, public_profile=True)
        return Response(get_public_trust_summary(space, viewer=request.user))


class JourneyFeedbackAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, journey_id):
        journey = get_object_or_404(Journey.objects.select_related("activity", "occurrence"), pk=journey_id, beneficiary=request.user)
        data = request.data
        try:
            feedback = submit_feedback(
                journey=journey,
                actor=request.user,
                delivery=data.get("delivery", "not_applicable"),
                timeliness=data.get("timeliness", "not_applicable"),
                access_experience=data.get("access_experience", "not_applicable"),
                accuracy=data.get("accuracy", "not_applicable"),
                overall_sentiment=data.get("overall_sentiment", ""),
                comment=data.get("comment", ""),
            )
        except (ValidationError, PermissionDenied) as exc:
            return _error_response(exc)
        return Response({"id": str(feedback.pk), "submitted_at": feedback.submitted_at}, status=201)


class JourneyReportAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, journey_id):
        journey = get_object_or_404(Journey.objects.select_related("activity", "occurrence", "activity__space"), pk=journey_id, beneficiary=request.user)
        try:
            report = create_report(actor=request.user, journey=journey, category=request.data.get("category", ""), description=request.data.get("description", ""))
        except (ValidationError, PermissionDenied) as exc:
            return _error_response(exc)
        return Response({"id": str(report.pk), "status": report.status, "created_at": report.created_at}, status=201)


class DisputeAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, dispute_id):
        dispute = get_object_or_404(Dispute.objects.select_related("report", "journey__activity", "respondent_space"), pk=dispute_id)
        if not dispute_visible_to(dispute, request.user):
            raise PermissionDenied("Accès au litige refusé.")
        return Response({
            "id": str(dispute.pk),
            "status": dispute.status,
            "decision_code": dispute.decision_code if dispute.status in {"decided", "closed"} else "",
            "decision_summary": dispute.decision_summary if dispute.status in {"decided", "closed"} else "",
            "remedy_code": dispute.remedy_code if dispute.status in {"decided", "closed"} else "",
            "created_at": dispute.created_at,
            "decided_at": dispute.decided_at,
            "closed_at": dispute.closed_at,
        })


class MyProofsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response([_proof_payload(proof) for proof in proofs_for_profile(request.user)])


class PublicProofAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, public_id):
        proof = public_proof_by_id(public_id)
        if proof is None:
            return Response({"detail": "Proof introuvable."}, status=404)
        payload = _proof_payload(proof)
        payload.pop("is_public", None)
        return Response(payload)
