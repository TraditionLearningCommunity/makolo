"""Mobile/API façade over the canonical Sharing domain.

No new sharing authority: public selection and permissions stay with Discovery
and sharing.services; tokens remain opaque to Flutter.
"""
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied, ValidationError as DomainValidationError
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import NotFound, Throttled, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import UserProfile
from activities.models import Activity, Occurrence
from discovery.api.composition import detail_projection
from opportunities.models import Opportunity
from core.web_throttling import allow_web_request, client_rate_identity, value_rate_identity

from .models import ShareIntent, ShareSubjectType
from .services import (
    ShareUnavailable,
    create_activity_share,
    create_direct_activity_share,
    create_opportunity_share,
    create_direct_opportunity_share,
    resolve_share_link,
    resolve_delivery_for_recipient,
    resolve_activity_share_subject,
    resolve_opportunity_share_subject,
    share_public_url,
    share_qr_url,
)
from .views import _recipient_candidates


def _limited(request, recipient=None):
    actor_id = str(request.user.pk)
    identities = [value_rate_identity("sender", actor_id)]
    if not allow_web_request(
        request, scope="sharing-mobile-minute", limit=12,
        window_seconds=60, identities=identities,
    ) or not allow_web_request(
        request, scope="sharing-mobile-hour", limit=60,
        window_seconds=3600, identities=identities,
    ):
        raise Throttled(detail="Trop de partages. Réessayez plus tard.")
    if recipient is not None and not allow_web_request(
        request, scope="sharing-direct-pair", limit=8,
        window_seconds=3600,
        identities=[value_rate_identity("pair", f"{actor_id}:{recipient.pk}")],
    ):
        raise Throttled(detail="Trop d'envois à ce Profil.")


class ShareRecipientSearchAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not allow_web_request(
            request, scope="sharing-profile-search", limit=30,
            window_seconds=60,
            identities=[
                value_rate_identity("profile", str(request.user.pk)),
                client_rate_identity(request),
            ],
        ):
            raise Throttled(detail="Recherche temporairement limitée.")
        query = (request.query_params.get("q") or "").strip()
        if len(query) > 100:
            raise ValidationError({"q": "Recherche trop longue."})
        _, profiles = _recipient_candidates(request)
        return Response({
            "results": [
                {"id": str(profile.pk),
                 "name": profile.user.full_name or profile.user.username,
                 "username": profile.user.username}
                for profile in profiles
            ]
        })


class SharePossibilityAPIView(APIView):
    permission_classes = [IsAuthenticated]
    ALLOWED = {"activity", "service_activity", "funding_activity", "opportunity"}

    def post(self, request, family, item_id):
        if family not in self.ALLOWED:
            raise NotFound("Possibilité indisponible.")
        # Owner selectors must authorize the same possibility as Discovery.
        projection = detail_projection(family, item_id, profile=request.user)
        if projection is None:
            raise NotFound("Possibilité indisponible.")
        recipient_id = request.data.get("recipient_id")
        if recipient_id is not None and not isinstance(recipient_id, str):
            raise ValidationError({"recipient_id": "Identifiant incorrect."})
        recipient = None
        if recipient_id:
            from uuid import UUID
            try:
                recipient_uuid = UUID(recipient_id)
            except (TypeError, ValueError) as exc:
                raise ValidationError({"recipient_id": "Identifiant incorrect."}) from exc
            recipient = get_object_or_404(
                UserProfile.objects.select_related("user").filter(
                    user__is_active=True, searchable=True,
                ),
                pk=recipient_uuid,
            )
        _limited(request, recipient)
        try:
            if family == "opportunity":
                opportunity = get_object_or_404(
                    Opportunity.objects.select_related("current_revision"),
                    pk=item_id,
                )
                if opportunity.current_revision is None:
                    raise ValidationError("Possibilité non partageable.")
                args = {
                    "created_by": request.user,
                    "opportunity_revision": opportunity.current_revision,
                    "intent": ShareIntent.VIEW,
                }
                created = (
                    create_direct_opportunity_share(recipient=recipient, **args)
                    if recipient else create_opportunity_share(**args)
                )
            else:
                activity = get_object_or_404(Activity, pk=item_id)
                occurrence = None
                occurrence_ref = projection["identity"].get("occurrence")
                if occurrence_ref:
                    occurrence = get_object_or_404(
                        Occurrence, pk=occurrence_ref["id"], activity=activity,
                    )
                args = {
                    "created_by": request.user,
                    "activity": activity,
                    "occurrence": occurrence,
                    "intent": ShareIntent.VIEW,
                }
                created = (
                    create_direct_activity_share(recipient=recipient, **args)
                    if recipient else create_activity_share(**args)
                )
        except (PermissionDenied, DomainValidationError) as exc:
            raise ValidationError({"share": str(exc)}) from exc
        if recipient:
            return Response({
                "state": "delivered",
                "delivery_id": str(created.delivery.pk),
            }, status=201)
        return Response({
            "state": "link",
            "url": share_public_url(created.raw_token),
            "qr_url": share_qr_url(created.raw_token),
            "title": projection["representation"]["title"],
            "text": projection["representation"].get("summary") or "",
        }, status=201)


def _public_discovery_destination(envelope):
    # Opaque Sharing identities only become N2 routes after owner/public checks.
    if envelope.subject_type == ShareSubjectType.ACTIVITY:
        _, activity, _ = resolve_activity_share_subject(envelope)
        for family in ("activity", "service_activity", "funding_activity"):
            if detail_projection(family, activity.pk, profile=AnonymousUser()) is not None:
                return family, str(activity.pk)
    elif envelope.subject_type == ShareSubjectType.OPPORTUNITY:
        _, opportunity, _, _ = resolve_opportunity_share_subject(envelope)
        if detail_projection(
            "opportunity", opportunity.pk, profile=AnonymousUser(),
        ) is not None:
            return "opportunity", str(opportunity.pk)
    raise ShareUnavailable


def _destination_response(envelope):
    family, id_ = _public_discovery_destination(envelope)
    response = Response({
        "family": family,
        "id": id_,
        "route": f"/discover/items/{family}/{id_}",
    })
    response["Cache-Control"] = "no-store"
    return response


class PublicShareResolveAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, token):
        if len(token) > 128:
            raise NotFound("Partage indisponible.")
        try:
            return _destination_response(resolve_share_link(token))
        except (ShareUnavailable, DomainValidationError) as exc:
            raise NotFound("Partage indisponible.") from exc


class ShareDeliveryResolveAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, delivery_id):
        try:
            delivery = resolve_delivery_for_recipient(
                delivery_id=delivery_id,
                user=request.user,
                mark_opened=True,
            )
            return _destination_response(delivery.envelope)
        except PermissionDenied:
            from rest_framework.exceptions import PermissionDenied as APIForbidden
            raise APIForbidden("Partage réservé au destinataire.")
        except (ShareUnavailable, DomainValidationError) as exc:
            raise NotFound("Partage indisponible.") from exc
