from __future__ import annotations

from django.core.exceptions import PermissionDenied, ValidationError as DjangoValidationError
from django.db import transaction
from django.http import FileResponse, Http404
from django.utils import timezone
from django.utils.text import slugify

from core.api.now_media_views import DOCX_MIME, MAX_DOCUMENT_TEXT, _docx_readable_text

from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from journeys.collaboration_services import ensure_case_access
from journeys.models import Journey
from personal_assets.forms import PersonalAssetCreateForm, PersonalAssetVersionForm
from personal_assets.models import PersonalAsset
from personal_assets.selectors import personal_asset_for_controller
from personal_assets.services import (
    archive_personal_asset,
    create_personal_asset,
    create_personal_asset_version,
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


def _form_errors(form):
    return {
        field: [item["message"] for item in errors]
        for field, errors in form.errors.get_json_data().items()
    }


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


class PersonalResourceCreateAPIView(PersonalProjectionAPIView):
    projection_code = "personal.resource.detail"

    def post(self, request):
        self._guard_personal_scope(request, include_body=True)
        form = PersonalAssetCreateForm(request.data, request.FILES)
        if not form.is_valid():
            raise ValidationError(_form_errors(form))
        try:
            with transaction.atomic():
                asset = create_personal_asset(
                    controller=request.user,
                    subject_profile=request.user,
                    title=form.cleaned_data["title"],
                    kind=form.cleaned_data["kind"],
                    sensitivity=form.cleaned_data["sensitivity"],
                )
                create_personal_asset_version(
                    actor=request.user,
                    asset=asset,
                    uploaded_file=form.cleaned_data["file"],
                    issued_at=form.cleaned_data["issued_at"],
                    expires_at=form.cleaned_data["expires_at"],
                )
        except DjangoValidationError as exc:
            fields = getattr(exc, "message_dict", None)
            raise ValidationError(
                fields or {"non_field_errors": exc.messages}
            ) from exc
        observed_at = timezone.now()
        response = self._response(
            build_personal_resource_detail_data(
                request.user,
                asset_id=asset.pk,
                observed_at=observed_at,
            ),
            observed_at=observed_at,
        )
        response.status_code = 201
        return response


class PersonalResourceVersionCreateAPIView(PersonalProjectionAPIView):
    projection_code = "personal.resource.detail"

    def post(self, request, pk):
        self._guard_personal_scope(request, include_body=True)
        try:
            asset = personal_asset_for_controller(request.user, pk)
        except PersonalAsset.DoesNotExist as exc:
            raise Http404 from exc
        form = PersonalAssetVersionForm(request.data, request.FILES)
        if not form.is_valid():
            raise ValidationError(_form_errors(form))
        try:
            create_personal_asset_version(
                actor=request.user,
                asset=asset,
                uploaded_file=form.cleaned_data["file"],
                issued_at=form.cleaned_data["issued_at"],
                expires_at=form.cleaned_data["expires_at"],
            )
        except (PermissionDenied, DjangoValidationError) as exc:
            fields = getattr(exc, "message_dict", None)
            if isinstance(exc, PermissionDenied):
                raise Http404 from exc
            raise ValidationError(
                fields or {"non_field_errors": exc.messages}
            ) from exc
        observed_at = timezone.now()
        response = self._response(
            build_personal_resource_detail_data(
                request.user,
                asset_id=asset.pk,
                observed_at=observed_at,
            ),
            observed_at=observed_at,
        )
        response.status_code = 201
        return response


class PersonalResourceArchiveAPIView(PersonalProjectionAPIView):
    projection_code = "personal.resource.detail"

    def post(self, request, pk):
        self._guard_personal_scope(request, include_body=True)
        try:
            asset = personal_asset_for_controller(request.user, pk)
            archive_personal_asset(actor=request.user, asset=asset)
        except PersonalAsset.DoesNotExist as exc:
            raise Http404 from exc
        except PermissionDenied as exc:
            raise Http404 from exc
        observed_at = timezone.now()
        return self._response(
            build_personal_resource_detail_data(
                request.user,
                asset_id=pk,
                observed_at=observed_at,
            ),
            observed_at=observed_at,
        )


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
        except PersonalAsset.DoesNotExist as exc:
            raise Http404 from exc
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

        if request.query_params.get("view") == "text":
            mime = (version.mime_type or "").lower().strip()
            if mime == DOCX_MIME:
                with version.file.open("rb") as source:
                    readable = _docx_readable_text(source)
            elif mime == "text/plain":
                with version.file.open("rb") as source:
                    raw = source.read(MAX_DOCUMENT_TEXT + 1)
                if len(raw) > MAX_DOCUMENT_TEXT:
                    raise Http404
                readable = raw.decode("utf-8", errors="replace")
            else:
                raise Http404
            response = HttpResponse(
                readable,
                content_type="text/plain; charset=utf-8",
            )
            response["Content-Security-Policy"] = "default-src 'none'; sandbox"
            response["Cross-Origin-Resource-Policy"] = "same-origin"
        else:
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
        self._guard_personal_scope(request, include_body=True)
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
                "satisfied_by_reuse": False,
                "decision_owner": "requirements_readiness",
                "note": "La réutilisation crée un JourneyArtifact ; elle ne décide pas la satisfaction d'un Requirement.",
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
