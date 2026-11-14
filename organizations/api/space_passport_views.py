"""Private operator API for the existing canonical Space Passport.

All mutations require SPACE_MANAGE. A Space VIEW mandate alone never issues,
shares or revokes collective documents. The same Sharing snapshots and PDF
renderer are reused for Profile and Space, without a second ownership model.
"""
from datetime import timezone as dt_timezone
from uuid import UUID

from django.core.exceptions import PermissionDenied as DomainDenied
from django.core.exceptions import ValidationError as DomainValidationError
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError, Throttled
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import UserProfile
from core.api.projections import projection_envelope
from core.api.me_projection import _passport_activity
from core.branding import render_makolo_qr_png
from core.web_throttling import allow_web_request, value_rate_identity
from organizations.models import Organization
from organizations.permissions import (
    user_can_access_organization_workspace,
    user_can_manage_organization,
    user_can_manage_organization_team,
)
from sharing.models import PassportSnapshot, PassportShareSubject, PublicIdentifier
from sharing.passport import (
    PASSPORT_COMPLETE, PASSPORT_PUBLIC, PASSPORT_VARIANTS,
    build_space_passport, space_passport_topic_options,
    space_has_public_passport,
)
from sharing.passport_documents import (
    issue_passport_snapshot, passport_verification_token,
    revoke_passport_snapshot, snapshot_payload_is_intact,
)
from sharing.passport_pdf import passport_pdf_response
from sharing.passport_pdf_layout import render_passport_layout
from sharing.passport_sharing import (
    create_passport_share, create_direct_passport_share, revoke_passport_share,
)


def _space(request, slug, *, mutate=False):
    space = get_object_or_404(Organization, slug=slug)
    # Never infer authority from TeamMembership, workspace choice or a
    # previous local snapshot. Server-side Mandate/Permission is mandatory.
    if mutate:
        allowed = user_can_manage_organization(request.user, space)
    else:
        allowed = user_can_access_organization_workspace(request.user, space)
    if not allowed:
        raise NotFound()
    return space


def _envelope(projection, data):
    response = Response(projection_envelope(
        projection=projection, data=data, generated_at=timezone.now(),
    ))
    response["Cache-Control"] = "private, no-store"
    return response


def _projection(space, request):
    variant = (request.query_params.get("variant") or PASSPORT_COMPLETE).strip()
    if variant not in PASSPORT_VARIANTS:
        raise ValidationError({"variant": "Variante inconnue."})
    try:
        return build_space_passport(
            space, variant=variant,
            topic_codes=request.query_params.getlist("topic"),
            selected_activity_ids=(
                request.query_params.getlist("activity")
                if variant == "custom" and "activity" in request.query_params else None
            ),
            selected_credential_ids=(
                request.query_params.getlist("credential")
                if variant == "custom" and "credential" in request.query_params else None
            ),
            selected_sections=(
                request.query_params.getlist("include")
                if variant == "custom" else None
            ),
            excluded_activity_ids=(
                request.query_params.getlist("exclude_activity")
                if variant == "custom" else ()
            ),
            excluded_credential_ids=(
                request.query_params.getlist("exclude_credential")
                if variant == "custom" else ()
            ),
            excluded_sections=(
                request.query_params.getlist("exclude")
                if variant == "custom" else ()
            ),
            include_private_teams=(
                variant == PASSPORT_COMPLETE
                and user_can_manage_organization_team(request.user, space)
            ),
        )
    except (ValueError, DomainDenied, DomainValidationError) as exc:
        raise ValidationError({"selection": "Sélection du Passeport invalide."}) from exc


def _document(snapshot):
    return {
        "id": str(snapshot.pk),
        "document_id": snapshot.document_id,
        "variant": snapshot.variant,
        "generated_at": snapshot.generated_at.isoformat(),
        "revoked": snapshot.is_revoked,
        "verification_path": reverse(
            "sharing:passport-verify",
            kwargs={"token": passport_verification_token(snapshot)},
        ),
    }


def _get_snapshot(space, snapshot_id):
    return get_object_or_404(
        PassportSnapshot.objects.select_related("space"),
        pk=snapshot_id, space=space,
    )


def _limit(request, space, action, limit=12):
    if not allow_web_request(
        request, scope="passport-space-" + action, limit=limit,
        window_seconds=60,
        identities=[
            value_rate_identity("actor", str(request.user.pk)),
            value_rate_identity("space", str(space.pk)),
        ],
    ):
        raise Throttled(detail="Trop de demandes.")


def _dated_pdf(request, snapshot):
    if not snapshot_payload_is_intact(snapshot):
        raise Http404("Document non intègre.")
    url = request.build_absolute_uri(reverse(
        "sharing:passport-verify",
        kwargs={"token": passport_verification_token(snapshot)},
    ))
    issued = snapshot.generated_at.astimezone(dt_timezone.utc)
    content = render_passport_layout(
        snapshot.payload,
        {
            "document_id": snapshot.document_id,
            "issued_at": issued.strftime("%d/%m/%Y · %H:%M UTC"),
            "variant": {
                "complete": "Complet", "public": "Public",
                "thematic": "Thématique", "custom": "Personnalisé",
            }.get(snapshot.variant, snapshot.variant),
            "identifier": snapshot.public_identifier,
        },
        url,
        qr_png=render_makolo_qr_png(url, branded=True, box_size=5),
    )
    response = HttpResponse(content, content_type="application/pdf")
    response["Content-Disposition"] = (
        f'attachment; filename="passeport-makolo-{snapshot.document_id}.pdf"'
    )
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response


class _SpacePassportAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def subject(self, request, slug, *, mutate=False):
        return _space(request, slug, mutate=mutate)


class SpacePassportAPIView(_SpacePassportAPIView):
    def get(self, request, slug):
        space = self.subject(request, slug)
        if not user_can_manage_organization(request.user, space):
            # An activity-scoped user cannot obtain the entire Space record.
            # The public form is still accessible through its own reader.
            raise NotFound()
        complete = build_space_passport(
            space, variant=PASSPORT_COMPLETE,
            include_private_teams=user_can_manage_organization_team(
                request.user, space,
            ),
        )
        public = build_space_passport(space, variant=PASSPORT_PUBLIC)
        topic_options = space_passport_topic_options(space)
        public_ids = {str(row.pk) for row in public.activities}
        public_identifier = PublicIdentifier.objects.filter(
            space=space,
        ).values_list("identifier", flat=True).first()
        payload = {
            "public_path": (
                reverse("public-passport", kwargs={"identifier": public_identifier})
                if public_identifier and space_has_public_passport(space)
                else None
            ),
            "subject_kind": "space",
            "subject_id": str(space.pk),
            "slug": space.slug,
            "public_profile_enabled": space_has_public_passport(space),
            "variant": "complete",
            "identity": {
                **complete.identity,
                "links": [
                    {"label": label, "url": url}
                    for label, url in complete.identity.get("links", ())
                ],
            },
            "activities": [_passport_activity(row) for row in complete.activities],
            "established": {
                "trust_verifications": [
                    {
                        "label": row.get_claim_type_display(),
                        "valid_until": (
                            row.valid_until.isoformat()
                            if row.valid_until else None
                        ),
                    }
                    for row in complete.trust_verifications
                ],
            },
            "issued": {
                "credential_summary": list(complete.credential_summary),
            },
            "collectives": {"space_teams": list(complete.space_teams)},
            "topic_options": [
                {"code": row.code, "label": row.label}
                for row in topic_options
            ],
            "composition": {
                "schema_version": 1,
                "public_identity": {
                    **public.identity,
                    "links": [
                        {"label": label, "url": url}
                        for label, url in public.identity.get("links", ())
                    ],
                },
                "public_ids": {"activities": sorted(public_ids)},
                "public_trust": [
                    {"label": row.get_claim_type_display()}
                    for row in public.trust_verifications
                ],
                "public_credentials": list(public.credential_summary),
            },
            "capabilities": {
                "issue": True,
                "edit": user_can_manage_organization(request.user, space),
                "teams": user_can_manage_organization_team(
                    request.user, space,
                ),
            },
        }
        return _envelope("space.passport", payload)


class SpacePassportPdfAPIView(_SpacePassportAPIView):
    def get(self, request, slug):
        space = self.subject(request, slug, mutate=True)
        _limit(request, space, "pdf", limit=8)
        return passport_pdf_response(request, _projection(space, request))


class SpacePassportIssueAPIView(_SpacePassportAPIView):
    def post(self, request, slug):
        space = self.subject(request, slug, mutate=True)
        _limit(request, space, "issue", limit=8)
        projection = _projection(space, request)
        if not projection.has_content:
            raise ValidationError({"selection": "Aucun contenu à émettre."})
        snapshot = issue_passport_snapshot(projection)
        return _envelope("space.passport.issuance", _document(snapshot))


class SpacePassportHistoryAPIView(_SpacePassportAPIView):
    def get(self, request, slug):
        space = self.subject(request, slug, mutate=True)
        try:
            offset = int(request.query_params.get("offset", "0"))
        except (TypeError, ValueError) as exc:
            raise ValidationError({"offset": "Entier attendu."}) from exc
        if offset < 0 or offset > 100000:
            raise ValidationError({"offset": "Décalage invalide."})
        qs = PassportSnapshot.objects.filter(space=space).prefetch_related(
            "passport_share_subjects__envelope",
        ).order_by("-generated_at", "-pk")
        items = list(qs[offset:offset + 20])
        return _envelope("space.passport.history", {
            "count": qs.count(),
            "items": [{
                **_document(snapshot),
                "integrity_ok": snapshot_payload_is_intact(snapshot),
                "active_shares": [{
                    "id": str(share.envelope_id),
                    "expires_at": (
                        share.envelope.expires_at.isoformat()
                        if share.envelope.expires_at else None
                    ),
                } for share in snapshot.passport_share_subjects.all()
                   if not snapshot.is_revoked and share.envelope.is_active_at()],
            } for snapshot in items],
            "has_more": offset + len(items) < qs.count(),
            "next_offset": offset + len(items),
        })


class SpacePassportVersionAPIView(_SpacePassportAPIView):
    def get(self, request, slug, snapshot_id):
        space = self.subject(request, slug, mutate=True)
        snapshot = _get_snapshot(space, snapshot_id)
        if not snapshot_payload_is_intact(snapshot):
            raise NotFound()
        # Team facts still require a distinct current authority.
        if snapshot.payload.get("space_teams") and not (
            user_can_manage_organization_team(request.user, space)
        ):
            raise NotFound()
        return _envelope("space.passport.version", {
            **_document(snapshot), "payload": snapshot.payload,
        })


class SpacePassportVersionPdfAPIView(_SpacePassportAPIView):
    def get(self, request, slug, snapshot_id):
        space = self.subject(request, slug, mutate=True)
        snapshot = _get_snapshot(space, snapshot_id)
        if snapshot.payload.get("space_teams") and not (
            user_can_manage_organization_team(request.user, space)
        ):
            raise NotFound()
        return _dated_pdf(request, snapshot)


class SpacePassportShareAPIView(_SpacePassportAPIView):
    def post(self, request, slug, snapshot_id):
        space = self.subject(request, slug, mutate=True)
        _limit(request, space, "share")
        snapshot = _get_snapshot(space, snapshot_id)
        try:
            days = int(request.data.get("days", 7))
            grant, url = create_passport_share(
                snapshot=snapshot, actor=request.user, days=days,
            )
        except (ValueError, TypeError, DomainValidationError, DomainDenied) as exc:
            raise ValidationError({"passport": "Partage indisponible."}) from exc
        return _envelope("space.passport.share", {
            "share_id": str(grant.pk),
            "share_url": url,
            "expires_at": grant.expires_at.isoformat(),
            "document_id": snapshot.document_id,
        })


class SpacePassportDirectShareAPIView(_SpacePassportAPIView):
    def post(self, request, slug, snapshot_id):
        space = self.subject(request, slug, mutate=True)
        recipient_id = request.data.get("recipient_id")
        try:
            recipient = get_object_or_404(
                UserProfile.objects.select_related("user").filter(
                    searchable=True, user__is_active=True,
                ),
                pk=UUID(str(recipient_id)),
            )
        except (TypeError, ValueError) as exc:
            raise ValidationError({"recipient_id": "Destinataire invalide."}) from exc
        _limit(request, space, "deliver")
        snapshot = _get_snapshot(space, snapshot_id)
        try:
            delivery = create_direct_passport_share(
                snapshot=snapshot, actor=request.user, recipient=recipient,
            )
        except (DomainValidationError, DomainDenied, ValueError) as exc:
            raise ValidationError({"passport": "Partage indisponible."}) from exc
        return _envelope("space.passport.delivery", {
            "delivery_id": str(delivery.pk),
            "recipient_id": str(recipient.pk),
            "document_id": snapshot.document_id,
        })


class SpacePassportVersionRevokeAPIView(_SpacePassportAPIView):
    def post(self, request, slug, snapshot_id):
        space = self.subject(request, slug, mutate=True)
        snapshot = _get_snapshot(space, snapshot_id)
        revoked = revoke_passport_snapshot(
            snapshot=snapshot, actor=request.user,
        )
        return _envelope("space.passport.version", _document(revoked))


class SpacePassportShareRevokeAPIView(_SpacePassportAPIView):
    def post(self, request, slug, share_id):
        space = self.subject(request, slug, mutate=True)
        grant = get_object_or_404(
            PassportShareSubject.objects.select_related("envelope"),
            envelope_id=share_id, snapshot__space=space,
        )
        revoked = revoke_passport_share(
            envelope=grant.envelope, actor=request.user,
        )
        return _envelope("space.passport.share", {
            "share_id": str(revoked.pk),
            "revoked": not revoked.is_active_at(),
        })
