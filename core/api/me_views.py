from django.utils import timezone
from uuid import UUID
from core.web_throttling import allow_web_request, value_rate_identity
from django.http import Http404, HttpResponse
from datetime import timezone as dt_timezone
from core.branding import render_makolo_qr_png
from sharing.passport_pdf_layout import render_passport_layout
from django.core.exceptions import ValidationError as DjangoValidationError, PermissionDenied as DjangoPermissionDenied
from django.shortcuts import get_object_or_404
from django.urls import reverse

from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from sharing.passport_pdf import passport_pdf_response
from sharing.models import PassportSnapshot, PassportShareSubject
from sharing.passport_documents import (
    passport_verification_token, snapshot_payload_is_intact,
    revoke_passport_snapshot, issue_passport_snapshot,
)
from sharing.passport_sharing import create_passport_share, revoke_passport_share, create_direct_passport_share
from accounts.models import UserProfile
from sharing.passport import build_profile_passport, PASSPORT_VARIANTS

from core.api.me_projection import (
    build_personal_resources_data,
    PASSPORT_COMPLETE,
    build_personal_collectives_data,
    build_personal_considerations_data,
    build_personal_me_data,
    build_personal_partners_data,
)
from core.api.projections import projection_envelope
from topics.models import OpenToKind, ProfileInterest, ProfileOpenTo, Topic
from topics.services import replace_profile_interests, replace_profile_open_to
from django.core.exceptions import ValidationError as DomainValidationError
from core.api.z8_projection import (
    RESOURCE_DEFAULT_LIMIT,
    RESOURCE_KIND_VALUES,
    RESOURCE_MAX_LIMIT,
    RESOURCE_SEARCH_MAX_LENGTH,
    RESOURCE_SENSITIVITY_VALUES,
    RESOURCE_SORT_VALUES,
    RESOURCE_VIEW_VALUES,
    build_personal_passport_depth_data,
    build_personal_resources_depth_data,
)


PERSONAL_SCOPE_OVERRIDE_KEYS = frozenset(
    {
        "profile_id",
        "user_id",
        "beneficiary_id",
        "subject_id",
        "act_as_space",
        "space_id",
        "space_context",
        "organization_actor",
    }
)


class PersonalProjectionAPIView(APIView):
    """Shared guard for private Mature projections rooted in request.user."""

    permission_classes = [IsAuthenticated]
    projection_code = ""

    def _guard_personal_scope(self, request, *, include_body=False):
        supplied = set(request.query_params.keys())
        if include_body and hasattr(request.data, "keys"):
            supplied.update(request.data.keys())
        blocked = sorted(PERSONAL_SCOPE_OVERRIDE_KEYS.intersection(supplied))
        if blocked:
            raise ValidationError(
                {
                    key: (
                        "Ce paramètre n'est pas accepté sur une projection "
                        "personnelle."
                    )
                    for key in blocked
                }
            )

    def _response(self, data, *, observed_at):
        response = Response(
            projection_envelope(
                projection=self.projection_code,
                data=data,
                generated_at=observed_at,
            )
        )
        response["Cache-Control"] = "private, no-store"
        return response


class PersonalMeAPIView(PersonalProjectionAPIView):
    """Private Mature projection for the authenticated person's Moi surface."""

    projection_code = "personal.me"

    def get(self, request):
        self._guard_personal_scope(request)
        observed_at = timezone.now()
        data = build_personal_me_data(
            profile=request.user,
            request=request,
            observed_at=observed_at,
        )
        return self._response(data, observed_at=observed_at)


class PersonalMeTerritoryPreviewAPIView(PersonalProjectionAPIView):
    """Bounded continuation of existing private N1 territory collections."""

    projection_code = "personal.me.preview"
    page_size = 24
    max_page_size = 50
    builders = {
        "considerations": build_personal_considerations_data,
        "collectives": build_personal_collectives_data,
        "resources": build_personal_resources_data,
    }

    families = {
        "considerations": frozenset((
            "interests", "open_to", "watches", "bookmarks",
            "followed_spaces", "followed_profiles",
        )),
        "collectives": frozenset(("authorized_spaces", "teams", "groups")),
        "resources": frozenset(("documents", "proofs", "credentials")),
    }

    def get(self, request, territory):
        self._guard_personal_scope(request)
        builder = self.builders.get(territory)
        family = request.query_params.get("family")
        if builder is None or family not in self.families.get(territory, ()):
            raise ValidationError({"family": "Collection inconnue."})
        try:
            offset = int(request.query_params.get("offset", 0))
            limit = int(request.query_params.get("limit", self.page_size))
        except (TypeError, ValueError) as exc:
            raise ValidationError({"pagination": "Paramètres invalides."}) from exc
        if offset < 0 or not 1 <= limit <= self.max_page_size:
            raise ValidationError({"pagination": "Plage de chargement invalide."})
        observed_at = timezone.now()
        collection = builder(request.user, offset=offset, limit=limit, family=family)[family]
        return self._response(
            {
                "actor": {"type": "profile", "id": str(request.user.pk)},
                "territory": territory,
                "family": family,
                "offset": offset,
                "limit": limit,
                "collection": collection,
            },
            observed_at=observed_at,
        )


class PersonalConsiderationsAPIView(PersonalProjectionAPIView):
    projection_code = "personal.me.considerations"

    def get(self, request):
        self._guard_personal_scope(request)
        observed_at = timezone.now()
        return self._response(
            build_personal_considerations_data(request.user),
            observed_at=observed_at,
        )


class PersonalConsiderationSettingsAPIView(PersonalProjectionAPIView):
    """Edit explicit personal preferences through their existing domain services.

    Saving interests cannot infer an openness, Watch, or follow.
    """

    projection_code = "personal.me.settings"

    def get(self, request):
        self._guard_personal_scope(request)
        query = (request.query_params.get("q") or "").strip()
        if len(query) > 100:
            raise ValidationError({"q": "Recherche trop longue."})
        return self._response(
            self._settings(request.user, query=query), observed_at=timezone.now(),
        )

    def put(self, request):
        self._guard_personal_scope(request, include_body=True)
        family = request.data.get("family")
        values = request.data.get("values")
        if family not in {"interests", "open_to"} or not isinstance(values, list) or len(values) > 200:
            raise ValidationError({"values": "Sélection invalide."})
        if any(not isinstance(value, str) for value in values):
            raise ValidationError({"values": "Sélection invalide."})
        # A client may explicitly choose how newly added declarations are
        # disclosed. Omission preserves the documented public-first behavior;
        # neither choice changes existing declarations or discoverability.
        new_visibility = request.data.get("new_visibility", "public")
        if new_visibility not in ("public", "private"):
            raise ValidationError({"new_visibility": "Visibilité initiale invalide."})
        try:
            if family == "interests":
                replace_profile_interests(
                    profile=request.user, topic_ids=values,
                    new_visibility=new_visibility,
                )
            else:
                retained = ProfileOpenTo.objects.filter(
                    profile=request.user, topic__isnull=True, kind__in=values,
                )
                public_kinds = list(
                    retained.filter(is_public=True).values_list("kind", flat=True)
                )
                if new_visibility == "public":
                    public_kinds.extend(
                        set(values) - set(retained.values_list("kind", flat=True))
                    )
                searchable_kinds = list(
                    retained.filter(is_searchable=True).values_list("kind", flat=True)
                )
                replace_profile_open_to(
                    profile=request.user, kinds=values,
                    public_kinds=public_kinds, searchable_kinds=searchable_kinds,
                )
        except DomainValidationError as exc:
            raise ValidationError(exc.message_dict if hasattr(exc, "message_dict") else {"values": exc.messages}) from exc
        return self._response(self._settings(request.user), observed_at=timezone.now())

    @staticmethod
    def _settings(profile, *, query=""):
        interests = ProfileInterest.objects.filter(profile=profile).values_list("topic_id", flat=True)
        open_to = ProfileOpenTo.objects.filter(
            profile=profile, is_active=True, topic__isnull=True,
        ).values_list("kind", flat=True)
        topics = Topic.objects.filter(is_active=True)
        if query:
            topics = topics.filter(label__icontains=query)
        topics = topics.order_by("label", "code")
        return {
            "topic_query": query,
            "topic_total": topics.count(),
            "interests": [str(value) for value in interests],
            "open_to": list(open_to),
            "selected_topics": [
                {"id": str(row.pk), "label": row.label}
                for row in Topic.objects.filter(pk__in=interests).order_by("label", "code")
            ],
            "topics": [
                {"id": str(row.pk), "label": row.label}
                for row in topics[:200]
            ],
            "open_to_options": [
                {"id": code, "label": label}
                for code, label in OpenToKind.choices
            ],
        }


class PersonalCollectivesAPIView(PersonalProjectionAPIView):
    projection_code = "personal.me.collectives"

    def get(self, request):
        self._guard_personal_scope(request)
        observed_at = timezone.now()
        return self._response(
            build_personal_collectives_data(request.user),
            observed_at=observed_at,
        )


class PersonalPassportAPIView(PersonalProjectionAPIView):
    projection_code = "personal.me.passport"

    def get(self, request):
        self._guard_personal_scope(request)
        observed_at = timezone.now()
        variant = (request.query_params.get("variant") or PASSPORT_COMPLETE).strip()
        try:
            data = build_personal_passport_depth_data(
                request.user,
                variant=variant,
                topic_codes=request.query_params.getlist("topic"),
                selected_activity_ids=request.query_params.getlist("activity"),
                selected_proof_ids=request.query_params.getlist("proof"),
                selected_credential_ids=request.query_params.getlist("credential"),
                selected_sections=request.query_params.getlist("include"),
                excluded_activity_ids=request.query_params.getlist("exclude_activity"),
                excluded_proof_ids=request.query_params.getlist("exclude_proof"),
                excluded_credential_ids=request.query_params.getlist("exclude_credential"),
                excluded_sections=request.query_params.getlist("exclude"),
            )
        except ValueError as exc:
            raise ValidationError({"variant": str(exc)}) from exc
        response = self._response(data, observed_at=observed_at)
        response["Cache-Control"] = "private, no-store"
        return response


def _selected_personal_passport(request):
    """One authorized builder for issue and PDF, never two document truths."""
    variant = (request.query_params.get("variant") or PASSPORT_COMPLETE).strip()
    if variant not in PASSPORT_VARIANTS:
        raise ValidationError({"variant": "Variante inconnue."})
    try:
        return build_profile_passport(
            request.user,
            variant=variant,
            topic_codes=request.query_params.getlist("topic"),
            selected_activity_ids=(
                request.query_params.getlist("activity") if variant == "custom" else None
            ),
            selected_proof_ids=(
                request.query_params.getlist("proof") if variant == "custom" else None
            ),
            selected_credential_ids=(
                request.query_params.getlist("credential") if variant == "custom" else None
            ),
            selected_sections=(
                request.query_params.getlist("include") if variant == "custom" else None
            ),
            excluded_activity_ids=(
                request.query_params.getlist("exclude_activity") if variant == "custom" else ()
            ),
            excluded_proof_ids=(
                request.query_params.getlist("exclude_proof") if variant == "custom" else ()
            ),
            excluded_credential_ids=(
                request.query_params.getlist("exclude_credential") if variant == "custom" else ()
            ),
            excluded_sections=(
                request.query_params.getlist("exclude") if variant == "custom" else ()
            ),
        )
    except ValueError as exc:
        raise ValidationError({"variant": str(exc)}) from exc
    except DjangoPermissionDenied as exc:
        raise ValidationError({"selection": "Sélection non autorisée."}) from exc


class PersonalPassportPdfAPIView(PersonalProjectionAPIView):
    """Authenticated PDF export also issues one immutable dated document."""

    projection_code = "personal.me.passport"

    def get(self, request):
        self._guard_personal_scope(request)
        return passport_pdf_response(request, _selected_personal_passport(request))


class PersonalPassportIssueAPIView(PersonalProjectionAPIView):
    """Issue one dated document without requiring the owner to download a PDF."""

    projection_code = "personal.me.passport.issuance"

    def post(self, request):
        self._guard_personal_scope(request, include_body=True)
        identity = [value_rate_identity("issuer", str(request.user.pk))]
        if not allow_web_request(
            request, scope="passport-issue-minute", limit=8,
            window_seconds=60, identities=identity,
        ):
            from rest_framework.exceptions import Throttled
            raise Throttled(detail="Trop d'émissions. Réessayez plus tard.")
        projection = _selected_personal_passport(request)
        if not projection.has_content:
            raise ValidationError({"selection": "Aucun contenu à émettre."})
        snapshot = issue_passport_snapshot(projection)
        return self._response({
            "id": str(snapshot.pk),
            "document_id": snapshot.document_id,
            "variant": snapshot.variant,
            "generated_at": snapshot.generated_at.isoformat(),
            "verification_path": reverse(
                "sharing:passport-verify",
                kwargs={"token": passport_verification_token(snapshot)},
            ),
        }, observed_at=timezone.now())


class PersonalPassportHistoryAPIView(PersonalProjectionAPIView):
    """Issued snapshots for the authenticated Profile, never other subjects."""
    projection_code = "personal.me.passport.history"

    def get(self, request):
        self._guard_personal_scope(request)
        try:
            offset = int(request.query_params.get("offset", "0"))
        except (TypeError, ValueError) as exc:
            raise ValidationError({"offset": "Entier attendu."}) from exc
        if offset < 0:
            raise ValidationError({"offset": "Décalage négatif interdit."})
        queryset = PassportSnapshot.objects.filter(profile=request.user).prefetch_related(
            "passport_share_subjects__envelope",
        ).order_by(
            "-generated_at", "-pk",
        )
        count = queryset.count()
        entries = list(queryset[offset : offset + 20])
        observed_at = timezone.now()
        return self._response(
            {
                "count": count,
                "items": [
                    {
                        "id": str(row.pk),
                        "document_id": row.document_id,
                        "variant": row.variant,
                        "generated_at": row.generated_at.isoformat(),
                        "revoked": row.is_revoked,
                        "integrity_ok": snapshot_payload_is_intact(row),
                        "active_shares": [
                            {
                                "id": str(grant.envelope_id),
                                "expires_at": (
                                    grant.envelope.expires_at.isoformat()
                                    if grant.envelope.expires_at else None
                                ),
                            }
                            for grant in row.passport_share_subjects.all()
                            if not row.is_revoked and grant.envelope.is_active_at()
                        ],
                        "verification_path": reverse(
                            "sharing:passport-verify",
                            kwargs={"token": passport_verification_token(row)},
                        ),
                    }
                    for row in entries
                ],
                "has_more": offset + len(entries) < count,
                "next_offset": offset + len(entries),
            },
            observed_at=observed_at,
        )


class PersonalPassportVersionAPIView(PersonalProjectionAPIView):
    """Read one exact issued payload without going through the live builder."""
    projection_code = "personal.me.passport.version"

    def get(self, request, snapshot_id):
        self._guard_personal_scope(request)
        snapshot = get_object_or_404(
            PassportSnapshot, pk=snapshot_id, profile=request.user,
        )
        if not snapshot_payload_is_intact(snapshot):
            raise Http404("Version non intègre.")
        return self._response(
            {
                "id": str(snapshot.pk),
                "document_id": snapshot.document_id,
                "revoked": snapshot.is_revoked,
                "variant": snapshot.variant,
                "generated_at": snapshot.generated_at.isoformat(),
                "payload": snapshot.payload,
                "verification_path": reverse(
                    "sharing:passport-verify",
                    kwargs={"token": passport_verification_token(snapshot)},
                ),
            },
            observed_at=timezone.now(),
        )


class PersonalPassportVersionPdfAPIView(PersonalProjectionAPIView):
    """Export an existing immutable snapshot; never issue a second version."""
    projection_code = "personal.me.passport.version"

    def get(self, request, snapshot_id):
        self._guard_personal_scope(request)
        snapshot = get_object_or_404(
            PassportSnapshot, pk=snapshot_id, profile=request.user,
        )
        if not snapshot_payload_is_intact(snapshot):
            raise Http404("Document non intègre.")
        verify_url = request.build_absolute_uri(reverse(
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
                    "complete": "Complet",
                    "public": "Public",
                    "thematic": "Thématique",
                    "custom": "Personnalisé",
                }.get(snapshot.variant, snapshot.variant),
                "identifier": snapshot.public_identifier,
            },
            verify_url,
            qr_png=render_makolo_qr_png(verify_url, branded=True, box_size=5),
        )
        response = HttpResponse(content, content_type="application/pdf")
        response["Content-Disposition"] = (
            f'attachment; filename="passeport-makolo-{snapshot.document_id}.pdf"'
        )
        response["Cache-Control"] = "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"
        return response


class PersonalPassportShareAPIView(PersonalProjectionAPIView):
    """Sharing grant for one existing issued document; never issues a new one."""
    projection_code = "personal.me.passport.share"

    def post(self, request, snapshot_id):
        self._guard_personal_scope(request, include_body=True)
        identity = [value_rate_identity("issuer", str(request.user.pk))]
        if not (
            allow_web_request(
                request, scope="passport-share-minute", limit=12,
                window_seconds=60, identities=identity,
            )
            and allow_web_request(
                request, scope="passport-share-hour", limit=60,
                window_seconds=3600, identities=identity,
            )
        ):
            from rest_framework.exceptions import Throttled
            raise Throttled(detail="Trop de partages. Réessayez plus tard.")
        snapshot = get_object_or_404(
            PassportSnapshot, pk=snapshot_id, profile=request.user,
        )
        try:
            days = int(request.data.get("days", 7))
            envelope, url = create_passport_share(
                snapshot=snapshot, actor=request.user, days=days,
            )
        except (TypeError, ValueError, DjangoValidationError) as exc:
            raise ValidationError(
                {"days": "Partage impossible : durée invalide ou document indisponible."}
            ) from exc
        except DjangoPermissionDenied as exc:
            raise Http404("Partage non autorisé.") from exc
        return self._response({
            "share_id": str(envelope.pk),
            "share_url": url,
            "expires_at": envelope.expires_at.isoformat(),
            "document_id": snapshot.document_id,
        }, observed_at=timezone.now())


class PersonalPassportDirectShareAPIView(PersonalProjectionAPIView):
    """Deliver an existing dated Passport to one recipient-bound Makolo account."""
    projection_code = "personal.me.passport.delivery"

    def post(self, request, snapshot_id):
        self._guard_personal_scope(request, include_body=True)
        recipient_id = request.data.get("recipient_id")
        if not isinstance(recipient_id, str):
            raise ValidationError({"recipient_id": "Destinataire requis."})
        try:
            recipient_uuid = UUID(recipient_id)
        except ValueError as exc:
            raise ValidationError({"recipient_id": "Identifiant incorrect."}) from exc
        recipient = get_object_or_404(
            UserProfile.objects.select_related("user").filter(
                user__is_active=True, searchable=True,
            ),
            pk=recipient_uuid,
        )
        actor_id = str(request.user.pk)
        if not (
            allow_web_request(
                request, scope="passport-direct-minute", limit=12,
                window_seconds=60,
                identities=[value_rate_identity("sender", actor_id)],
            )
            and allow_web_request(
                request, scope="passport-direct-pair", limit=8,
                window_seconds=3600,
                identities=[value_rate_identity(
                    "pair", f"{actor_id}:{recipient.pk}",
                )],
            )
        ):
            from rest_framework.exceptions import Throttled
            raise Throttled(detail="Trop de partages.")
        snapshot = get_object_or_404(
            PassportSnapshot, pk=snapshot_id, profile=request.user,
        )
        try:
            delivery = create_direct_passport_share(
                snapshot=snapshot, actor=request.user, recipient=recipient,
            )
        except (DjangoValidationError, DjangoPermissionDenied, ValueError) as exc:
            raise ValidationError({"passport": "Partage indisponible."}) from exc
        return self._response({
            "state": "delivered",
            "delivery_id": str(delivery.pk),
            "recipient_id": str(recipient.pk),
            "document_id": snapshot.document_id,
        }, observed_at=timezone.now())


class PersonalPassportVersionRevokeAPIView(PersonalProjectionAPIView):
    """Owner-only withdrawal of one issued snapshot and its active grants."""

    projection_code = "personal.me.passport.version"

    def post(self, request, snapshot_id):
        self._guard_personal_scope(request, include_body=True)
        snapshot = get_object_or_404(
            PassportSnapshot, pk=snapshot_id, profile=request.user,
        )
        revoked = revoke_passport_snapshot(snapshot=snapshot, actor=request.user)
        return self._response({
            "id": str(revoked.pk),
            "document_id": revoked.document_id,
            "revoked": revoked.is_revoked,
        }, observed_at=timezone.now())


class PersonalPassportShareRevokeAPIView(PersonalProjectionAPIView):
    """Revoke only a Sharing grant belonging to the current Profile."""

    projection_code = "personal.me.passport.share"

    def post(self, request, share_id):
        self._guard_personal_scope(request, include_body=True)
        grant = get_object_or_404(
            PassportShareSubject.objects.select_related("envelope"),
            envelope_id=share_id, snapshot__profile=request.user,
        )
        revoked = revoke_passport_share(
            envelope=grant.envelope, actor=request.user,
        )
        return self._response({
            "share_id": str(revoked.pk),
            "revoked": not revoked.is_active_at(),
        }, observed_at=timezone.now())


class PersonalResourcesAPIView(PersonalProjectionAPIView):
    projection_code = "personal.me.resources"

    def get(self, request):
        self._guard_personal_scope(request)
        observed_at = timezone.now()
        query = (request.query_params.get("q") or "").strip()
        if len(query) > RESOURCE_SEARCH_MAX_LENGTH:
            raise ValidationError(
                {
                    "q": (
                        f"La recherche ne peut pas dépasser "
                        f"{RESOURCE_SEARCH_MAX_LENGTH} caractères."
                    )
                }
            )
        view = request.query_params.get("view", "current")
        sort = request.query_params.get("sort", "recent")
        kind = request.query_params.get("kind", "")
        sensitivity = request.query_params.get("sensitivity", "")
        if view not in RESOURCE_VIEW_VALUES:
            raise ValidationError({"view": "Vue de documents inconnue."})
        if sort not in RESOURCE_SORT_VALUES:
            raise ValidationError({"sort": "Tri de documents inconnu."})
        if kind and kind not in RESOURCE_KIND_VALUES:
            raise ValidationError({"kind": "Type de document inconnu."})
        if sensitivity and sensitivity not in RESOURCE_SENSITIVITY_VALUES:
            raise ValidationError({"sensitivity": "Sensibilité inconnue."})
        try:
            limit = int(request.query_params.get("limit", RESOURCE_DEFAULT_LIMIT))
            offset = int(request.query_params.get("offset", 0))
        except (TypeError, ValueError) as exc:
            raise ValidationError(
                {"pagination": "limit et offset doivent être des entiers."}
            ) from exc
        if limit < 1 or limit > RESOURCE_MAX_LIMIT:
            raise ValidationError(
                {"limit": f"Ce paramètre doit être compris entre 1 et {RESOURCE_MAX_LIMIT}."}
            )
        if offset < 0:
            raise ValidationError(
                {"offset": "Ce paramètre doit être supérieur ou égal à 0."}
            )
        response = self._response(
            build_personal_resources_depth_data(
                request.user,
                observed_at=observed_at,
                query=query,
                view=view,
                kind=kind,
                sensitivity=sensitivity,
                sort=sort,
                limit=limit,
                offset=offset,
            ),
            observed_at=observed_at,
        )
        response["Cache-Control"] = "private, no-store"
        return response


class PersonalPartnersAPIView(PersonalProjectionAPIView):
    projection_code = "personal.me.partners"

    def get(self, request):
        self._guard_personal_scope(request)
        observed_at = timezone.now()
        return self._response(
            build_personal_partners_data(request.user),
            observed_at=observed_at,
        )
