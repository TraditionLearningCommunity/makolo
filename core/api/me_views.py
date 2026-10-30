from django.utils import timezone
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.urls import reverse

from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from sharing.passport_pdf import passport_pdf_response
from sharing.models import PassportSnapshot
from sharing.passport_documents import passport_verification_token, snapshot_payload_is_intact
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
    RESOURCE_MAX_LIMIT,
    RESOURCE_SEARCH_MAX_LENGTH,
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
        try:
            if family == "interests":
                replace_profile_interests(profile=request.user, topic_ids=values)
            else:
                retained = ProfileOpenTo.objects.filter(
                    profile=request.user, topic__isnull=True, kind__in=values,
                )
                public_kinds = list(
                    retained.filter(is_public=True).values_list("kind", flat=True)
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
            )
        except ValueError as exc:
            raise ValidationError({"variant": str(exc)}) from exc
        response = self._response(data, observed_at=observed_at)
        response["Cache-Control"] = "private, no-store"
        return response


class PersonalPassportPdfAPIView(PersonalProjectionAPIView):
    """Native authenticated PDF export; same owner, selection and privacy rules."""

    projection_code = "personal.me.passport"

    def get(self, request):
        self._guard_personal_scope(request)
        variant = (request.query_params.get("variant") or PASSPORT_COMPLETE).strip()
        if variant not in PASSPORT_VARIANTS:
            raise ValidationError({"variant": "Variante inconnue."})
        try:
            projection = build_profile_passport(
                request.user,
                variant=variant,
                topic_codes=request.query_params.getlist("topic"),
                selected_activity_ids=(
                    request.query_params.getlist("activity")
                    if variant == "custom" else None
                ),
                selected_proof_ids=(
                    request.query_params.getlist("proof")
                    if variant == "custom" else None
                ),
                selected_credential_ids=(
                    request.query_params.getlist("credential")
                    if variant == "custom" else None
                ),
                selected_sections=(
                    request.query_params.getlist("include")
                    if variant == "custom" else None
                ),
            )
        except ValueError as exc:
            raise ValidationError({"variant": str(exc)}) from exc
        return passport_pdf_response(request, projection)



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
        queryset = PassportSnapshot.objects.filter(profile=request.user).order_by(
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
