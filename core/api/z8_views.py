from __future__ import annotations

from django.core.exceptions import PermissionDenied, ValidationError as DjangoValidationError
from django.http import FileResponse, Http404
from django.utils import timezone
from django.utils.text import slugify

from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from journeys.collaboration_services import ensure_case_access
from journeys.models import Journey
from personal_assets.services import (
    personal_asset_version_for_download,
    use_personal_asset_version_in_journey,
)

from core.api.me_views import PersonalProjectionAPIView
from core.api.projections import projection_envelope
from core.api.z8_projection import (
    RESOURCE_DEFAULT_LIMIT,
    RESOURCE_MAX_LIMIT,
    RESOURCE_SEARCH_MAX_LENGTH,
    RESOURCE_VERSION_DEFAULT_LIMIT,
    RESOURCE_VERSION_MAX_LIMIT,
    build_personal_group_detail_data,
    build_personal_resource_detail_data,
)


def _integer_param(request, name, *, default, minimum=0, maximum=None):
    raw = request.query_params.get(name)
    if raw is None or raw == "":
        return default
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise ValidationError({name: "Ce paramètre doit être un entier."}) from exc
    if value < minimum:
        raise ValidationError(
            {name: f"Ce paramètre doit être supérieur ou égal à {minimum}."}
        )
    if maximum is not None and value > maximum:
        raise ValidationError(
            {name: f"Ce paramètre ne peut pas dépasser {maximum}."}
        )
    return value


class PersonalResourceDetailAPIView(PersonalProjectionAPIView):
    projection_code = "personal.resource.detail"

    def get(self, request, pk):
        self._guard_personal_scope(request)
        observed_at = timezone.now()
        version_limit = _integer_param(
            request,
            "version_limit",
            default=RESOURCE_VERSION_DEFAULT_LIMIT,
            minimum=1,
            maximum=RESOURCE_VERSION_MAX_LIMIT,
        )
        version_offset = _integer_param(
            request,
            "version_offset",
            default=0,
            minimum=0,
        )
        try:
            data = build_personal_resource_detail_data(
                request.user,
                asset_id=pk,
                observed_at=observed_at,
                version_limit=version_limit,
                version_offset=version_offset,
            )
        except Exception as exc:
            from personal_assets.models import PersonalAsset

            if isinstance(exc, PersonalAsset.DoesNotExist):
                raise Http404 from exc
            raise
        response = self._response(data, observed_at=observed_at)
        response["Cache-Control"] = "private, no-store"
        return response


class PersonalResourceVersionDownloadAPIView(PersonalProjectionAPIView):
    projection_code = "personal.resource.version.download"

    def get(self, request, version_id):
        self._guard_personal_scope(request)
        try:
            version = personal_asset_version_for_download(
                actor=request.user,
                version_id=version_id,
            )
        except PermissionDenied as exc:
            raise Http404 from exc

        response = FileResponse(
            version.file.open("rb"),
            as_attachment=True,
            filename=(
                f"{slugify(version.asset.title) or 'document'}"
                f"-v{version.version}"
            ),
            content_type=version.mime_type,
        )
        response["X-Content-Type-Options"] = "nosniff"
        response["Cache-Control"] = "private, no-store"
        return response


class PersonalResourceVersionReuseAPIView(PersonalProjectionAPIView):
    projection_code = "personal.resource.reuse"

    def post(self, request, version_id):
        self._guard_personal_scope(request)
        journey_id = request.data.get("journey_id")
        if not journey_id:
            raise ValidationError({"journey_id": "Ce champ est obligatoire."})

        journey = (
            Journey.objects.select_related("activity")
            .filter(pk=journey_id)
            .first()
        )
        if journey is None:
            raise Http404

        try:
            ensure_case_access(request.user, journey, write=False)
            version = personal_asset_version_for_download(
                actor=request.user,
                version_id=version_id,
            )
            artifact = use_personal_asset_version_in_journey(
                actor=request.user,
                personal_asset_version=version,
                journey=journey,
            )
        except PermissionDenied as exc:
            raise Http404 from exc
        except DjangoValidationError as exc:
            fields = getattr(exc, "message_dict", None)
            raise ValidationError(fields or {"non_field_errors": exc.messages}) from exc

        observed_at = timezone.now()
        data = {
            "source": {
                "kind": "personal_asset_version",
                "id": str(version.pk),
                "asset_id": str(version.asset_id),
                "version": version.version,
            },
            "result": {
                "kind": "journey_artifact",
                "id": str(artifact.pk),
                "journey_id": str(journey.pk),
            },
            "requirement": {
                "satisfied": False,
                "decision_owner": "requirements_readiness",
                "note": "La réutilisation crée un JourneyArtifact ; elle ne satisfait aucun Requirement par elle-même.",
            },
        }
        return Response(
            projection_envelope(
                projection=self.projection_code,
                data=data,
                generated_at=observed_at,
            ),
            status=201,
        )


class PersonalGroupDetailAPIView(PersonalProjectionAPIView):
    projection_code = "personal.group.detail"

    def get(self, request, pk):
        self._guard_personal_scope(request)
        observed_at = timezone.now()
        data = build_personal_group_detail_data(request.user, group_id=pk)
        if data is None:
            raise Http404
        response = self._response(data, observed_at=observed_at)
        response["Cache-Control"] = "private, no-store"
        return response
