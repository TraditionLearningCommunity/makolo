from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.status import HTTP_400_BAD_REQUEST, HTTP_403_FORBIDDEN
from rest_framework.views import APIView

from activities.models import Activity, Occurrence
from journeys.models import Journey

from .credential_models import Credential
from .credential_selectors import credentials_for_profile, public_credential_by_id
from .credential_services import can_issue_credential, issue_credential, revoke_credential


User = get_user_model()


def _error_response(exc):
    status = HTTP_403_FORBIDDEN if isinstance(exc, PermissionDenied) else HTTP_400_BAD_REQUEST
    if hasattr(exc, "message_dict"):
        detail = exc.message_dict
    else:
        detail = getattr(exc, "messages", [str(exc)])
    return Response({"detail": detail}, status=status)


def credential_payload(credential, *, public=False):
    issuer_type = "space" if credential.issuer_space_id else "profile"
    payload = {
        "public_id": str(credential.public_id),
        "credential_type": credential.credential_type,
        "title": credential.title,
        "statement": credential.statement,
        "status": credential.status,
        "verification_state": credential.verification_state,
        "issued_at": credential.issued_at,
        "revoked_at": credential.revoked_at,
        "beneficiary": {"name": credential.subject_display_name},
        "issuer": {
            "type": issuer_type,
            "name": credential.issuer_display_name,
        },
        "source": {
            "activity": {"title": credential.activity.title},
            "occurrence": (
                {"label": credential.occurrence.label}
                if credential.occurrence_id
                else None
            ),
        },
    }
    if not public:
        payload["id"] = str(credential.pk)
        payload["beneficiary"]["id"] = str(credential.subject_profile_id)
        payload["issuer"]["id"] = str(
            credential.issuer_space_id or credential.issuer_profile_id
        )
        payload["source"]["activity"]["id"] = str(credential.activity_id)
        payload["source"]["occurrence_id"] = (
            str(credential.occurrence_id) if credential.occurrence_id else None
        )
        payload["source"]["journey_id"] = (
            str(credential.journey_id) if credential.journey_id else None
        )
        payload["revoked_by_id"] = (
            str(credential.revoked_by_id) if credential.revoked_by_id else None
        )
        payload["revoke_reason"] = credential.revoke_reason
    return payload


class ActivityCredentialIssueAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, activity_id):
        activity = get_object_or_404(
            Activity.objects.select_related("space", "owner_profile"),
            pk=activity_id,
        )
        if not can_issue_credential(actor=request.user, activity=activity):
            return _error_response(
                PermissionDenied(
                    "Un Mandate autorisant la gestion de cette Activity ou de son Trust est requis."
                )
            )

        subject_profile_id = request.data.get("subject_profile_id")
        if not subject_profile_id:
            return Response({"detail": ["subject_profile_id est requis."]}, status=HTTP_400_BAD_REQUEST)
        subject_profile = get_object_or_404(User, pk=subject_profile_id)

        journey = None
        journey_id = request.data.get("journey_id")
        if journey_id:
            journey = get_object_or_404(
                Journey.objects.select_related("beneficiary", "activity", "occurrence"),
                pk=journey_id,
            )

        occurrence = None
        occurrence_id = request.data.get("occurrence_id")
        if occurrence_id:
            occurrence = get_object_or_404(Occurrence.objects.select_related("activity"), pk=occurrence_id)

        try:
            credential = issue_credential(
                activity=activity,
                subject_profile=subject_profile,
                credential_type=request.data.get("credential_type", ""),
                actor=request.user,
                journey=journey,
                occurrence=occurrence,
                title=request.data.get("title", ""),
                statement=request.data.get("statement", ""),
            )
        except (ValidationError, PermissionDenied) as exc:
            return _error_response(exc)
        return Response(credential_payload(credential), status=201)


class CredentialRevokeAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, credential_id):
        credential = get_object_or_404(
            Credential.objects.select_related("activity__space", "activity__owner_profile"),
            pk=credential_id,
        )
        try:
            credential = revoke_credential(
                credential=credential,
                actor=request.user,
                reason=request.data.get("reason", ""),
            )
        except (ValidationError, PermissionDenied) as exc:
            return _error_response(exc)
        return Response(credential_payload(credential))


class MyCredentialsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(
            [credential_payload(credential) for credential in credentials_for_profile(request.user)]
        )


class PublicCredentialAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, public_id):
        credential = public_credential_by_id(public_id)
        if credential is None:
            return Response({"detail": "Attestation inconnue ou invalide."}, status=404)
        return Response(credential_payload(credential, public=True))
