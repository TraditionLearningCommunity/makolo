"""Read-only native reader for issued Passport documents.

Issuance, public verification, and explicit Sharing remain separate. The
reader does not mint credentials, create a grant, or recompute dated content.
"""
from django.core import signing
from django.core.exceptions import ObjectDoesNotExist
from rest_framework.exceptions import NotFound
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.api.projections import projection_envelope
from .api_views import SharingNoStoreBoundary
from .passport_documents import (
    resolve_passport_verification_token, snapshot_payload_is_intact,
)
from .passport_sharing import resolve_passport_share
from .passport_views import (
    _snapshot_content_allowed, snapshot_subject_public_now,
)
from .services import ShareUnavailable, resolve_delivery_for_recipient
from django.core.exceptions import PermissionDenied


def _issued_document_response(*, snapshot, viewer, envelope=None):
    """Only the original, authorized issued payload may cross this boundary."""
    intact = snapshot_payload_is_intact(snapshot)
    public_now = snapshot_subject_public_now(snapshot)
    explicit_grant = envelope is not None
    allowed = (
        intact and not snapshot.is_revoked
        if explicit_grant else _snapshot_content_allowed(
            snapshot, viewer, currently_public=public_now,
        )
    )
    response = Response(projection_envelope(
        projection="sharing.passport.document",
        scope="reader",
        data={
            "document_id": snapshot.document_id,
            "subject_kind": snapshot.subject_kind,
            "public_identifier": snapshot.public_identifier,
            "variant": snapshot.variant,
            "issued_at": snapshot.generated_at.isoformat(),
            "revoked": snapshot.is_revoked,
            "integrity_ok": intact,
            "can_view_content": bool(allowed),
            "explicit_share": explicit_grant,
            "expires_at": (
                envelope.expires_at.isoformat()
                if explicit_grant and envelope.expires_at else None
            ),
            "payload": snapshot.payload if allowed else None,
        },
    ))
    return response


class PassportVerificationReaderAPIView(SharingNoStoreBoundary, APIView):
    """A signed verification address proves issuance, not a viewing right."""

    permission_classes = [AllowAny]

    def get(self, request, token):
        if len(token) > 4096:
            raise NotFound("Document indisponible.")
        try:
            snapshot = resolve_passport_verification_token(token)
        except (
            signing.BadSignature, ObjectDoesNotExist, KeyError, ValueError,
            TypeError,
        ) as exc:
            raise NotFound("Document indisponible.") from exc
        return _issued_document_response(snapshot=snapshot, viewer=request.user)


class PassportSharedReaderAPIView(SharingNoStoreBoundary, APIView):
    """A live, explicitly issued Sharing grant reveals only its dated version."""

    permission_classes = [AllowAny]

    def get(self, request, token):
        if len(token) > 256:
            raise NotFound("Partage indisponible.")
        try:
            envelope, snapshot = resolve_passport_share(token)
        except ShareUnavailable as exc:
            raise NotFound("Partage indisponible.") from exc
        return _issued_document_response(
            snapshot=snapshot, viewer=request.user, envelope=envelope,
        )


class PassportDeliveryReaderAPIView(SharingNoStoreBoundary, APIView):
    """Recipient-bound reader; a delivery never transfers the issuer's session."""
    permission_classes = [IsAuthenticated]

    def get(self, request, delivery_id):
        try:
            delivery = resolve_delivery_for_recipient(
                delivery_id=delivery_id, user=request.user, mark_opened=True,
            )
        except PermissionDenied as exc:
            from rest_framework.exceptions import PermissionDenied as Forbidden
            raise Forbidden("Partage réservé au destinataire.") from exc
        except ShareUnavailable as exc:
            raise NotFound("Partage indisponible.") from exc
        return _issued_document_response(
            snapshot=delivery.envelope.passport_subject.snapshot,
            viewer=request.user, envelope=delivery.envelope,
        )
