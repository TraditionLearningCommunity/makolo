"""Authenticated JourneyArtifact API: owner-backed, Profile/Space-scoped.

No public storage URLs or fake Readiness transitions. Uploads use existing
Journey collaboration services, file signature checks, and version audits.
"""
from django.core.exceptions import PermissionDenied as DomainPermissionDenied
from django.core.exceptions import ValidationError as DomainValidationError
from django.db import IntegrityError
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from django.utils.text import slugify
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from journeys import collaboration_services as owner
from journeys.collaboration_models import (
    JourneyArtifact, JourneyArtifactKind, JourneyArtifactSensitivity,
    JourneyArtifactStatus, JourneyStep,
)
from journeys.models import Journey
from services.space_beneficiary import (
    can_act_for_space_service_journey,
    can_read_space_service_journey,
)

EXTENSION_BY_MIME = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/msword": ".doc",
    "text/plain": ".txt",
    "image/jpeg": ".jpg",
    "image/png": ".png",
}
DOWNLOAD_KINDS = {
    JourneyArtifactKind.CV, JourneyArtifactKind.COVER_LETTER,
    JourneyArtifactKind.CERTIFICATE, JourneyArtifactKind.TRANSCRIPT,
    JourneyArtifactKind.RECOMMENDATION, JourneyArtifactKind.FORM,
}


def _reply(data, *, status=200):
    response = Response(data, status=status)
    response["Cache-Control"] = "private, no-store"
    return response


def _journey_for_actor(request, journey_id, *, slug=None, write=False):
    if slug is None:
        journey = get_object_or_404(
            Journey.objects.select_related("activity", "beneficiary"),
            pk=journey_id, beneficiary=request.user,
        )
        return journey
    from services.space_beneficiary_api import _journey as space_journey

    _space, journey = space_journey(
        request, slug, journey_id, write=write,
    )
    if not can_read_space_service_journey(request.user, journey):
        raise NotFound()
    return journey


def _collection_path(journey, *, slug=None):
    if slug is None:
        return f"/api/v1/me/journeys/{journey.pk}/artifacts/"
    return f"/api/v1/organizations/workspaces/{slug}/beneficiary/journeys/{journey.pk}/artifacts/"


def _visible_artifact(request, journey, artifact_id):
    artifact = (
        owner.artifacts_for_actor(actor=request.user, journey=journey)
        .filter(pk=artifact_id)
        .first()
    )
    if artifact is None:
        raise NotFound()
    return artifact


def _may_download(request, journey, artifact):
    if artifact.kind not in DOWNLOAD_KINDS:
        return False
    if artifact.status == JourneyArtifactStatus.SUPERSEDED or not artifact.file:
        return False
    if journey.beneficiary_space_id:
        return can_act_for_space_service_journey(request.user, journey)
    from sharing.document_services import can_export_journey_artifact

    return can_export_journey_artifact(
        request.user, artifact, channel="download",
    ).allowed


def _serialize(request, journey, artifact, *, slug=None):
    base = _collection_path(journey, slug=slug)
    can_write = (
        journey.beneficiary_id == request.user.pk
        if slug is None else
        can_act_for_space_service_journey(request.user, journey)
    )
    return {
        "id": str(artifact.pk),
        "journey_id": str(journey.pk),
        "step_id": str(artifact.step_id) if artifact.step_id else None,
        "title": artifact.title,
        "kind": artifact.kind,
        "status": artifact.status,
        "version": artifact.version,
        "sensitivity": artifact.sensitivity,
        "size": artifact.size,
        "mime_type": artifact.mime_type,
        "uploaded_at": artifact.uploaded_at.isoformat(),
        "supersedes_id": str(artifact.supersedes_id) if artifact.supersedes_id else None,
        "reviews": [
            {"status": review.status, "decided_at": review.decided_at.isoformat() if review.decided_at else None}
            for review in artifact.reviews.all()
        ],
        "capabilities": {
            "download": _may_download(request, journey, artifact),
            "download_requires_confirmation": _may_download(request, journey, artifact),
            "new_version": can_write and artifact.status != JourneyArtifactStatus.SUPERSEDED,
        },
        "links": {
            "download": base + str(artifact.pk) + "/download/"
            if _may_download(request, journey, artifact) else None,
            "versions": base + str(artifact.pk) + "/versions/"
            if can_write and artifact.status != JourneyArtifactStatus.SUPERSEDED else None,
        },
    }


def _file_params(request, journey, *, allow_step=True):
    uploaded = request.FILES.get("file")
    title = request.data.get("title", "")
    kind = request.data.get("kind", JourneyArtifactKind.OTHER)
    sensitivity = request.data.get(
        "sensitivity", JourneyArtifactSensitivity.SENSITIVE,
    )
    if not isinstance(title, str) or not title.strip() or len(title) > 220:
        raise ValidationError({"title": "Titre obligatoire (220 caractères maximum)."})
    if kind not in JourneyArtifactKind.values:
        raise ValidationError({"kind": "Type de pièce invalide."})
    if sensitivity not in JourneyArtifactSensitivity.values:
        raise ValidationError({"sensitivity": "Sensibilité invalide."})
    if kind == JourneyArtifactKind.IDENTITY_DOCUMENT and sensitivity != JourneyArtifactSensitivity.RESTRICTED:
        raise ValidationError({"sensitivity": "Un document d’identité doit rester restreint."})
    step = None
    if allow_step and request.data.get("step_id"):
        step = JourneyStep.objects.filter(
            journey=journey, pk=request.data["step_id"],
        ).first()
        if step is None:
            raise ValidationError({"step_id": "Étape inaccessible pour cette démarche."})
    elif not allow_step and request.data.get("step_id"):
        raise ValidationError({"step_id": "Une nouvelle version conserve son étape."})
    try:
        _data, _mime, sha256 = owner.validate_artifact_upload(uploaded)
    except DomainValidationError as exc:
        raise ValidationError(getattr(exc, "message_dict", None) or exc.messages) from exc
    return uploaded, title.strip(), kind, sensitivity, step, sha256


class JourneyArtifactCollectionAPIView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get(self, request, journey_id, slug=None):
        journey = _journey_for_actor(request, journey_id, slug=slug)
        artifacts = list(
            owner.artifacts_for_actor(actor=request.user, journey=journey)
            .prefetch_related("reviews")
            .order_by("-created_at", "-version", "id")[:150]
        )
        return _reply({
            "owner": {"kind": "journey", "id": str(journey.pk)},
            "beneficiary": (
                {"kind": "space", "id": str(journey.beneficiary_space_id)}
                if slug is not None else
                {"kind": "profile", "id": str(request.user.pk)}
            ),
            "artifacts": [
                _serialize(request, journey, artifact, slug=slug)
                for artifact in artifacts
            ],
            "has_more": (
                owner.artifacts_for_actor(actor=request.user, journey=journey).count() > 150
            ),
            "capabilities": {
                "upload": (
                    journey.beneficiary_id == request.user.pk
                    if slug is None else
                    can_act_for_space_service_journey(request.user, journey)
                ),
            },
        })

    def post(self, request, journey_id, slug=None):
        journey = _journey_for_actor(request, journey_id, slug=slug, write=True)
        if slug is not None and not can_act_for_space_service_journey(request.user, journey):
            raise NotFound()
        if set(request.data.keys()) - {
            "title", "kind", "sensitivity", "step_id", "file",
        }:
            raise ValidationError({"fields": "Champs inconnus."})
        uploaded, title, kind, sensitivity, step, content_hash = _file_params(request, journey)
        # Existing uniqueness is Journey + kind + title + version; identical
        # retries are safely replayed. Different bytes never silently replace.
        existing = JourneyArtifact.objects.filter(
            journey=journey, kind=kind, title=title, version=1,
        ).first()
        if existing is not None:
            if existing.content_hash != content_hash or existing.sensitivity != sensitivity or existing.step_id != (step.pk if step else None):
                return _reply({"code": "artifact_conflict", "detail": "Une pièce de même titre existe avec un autre contenu."}, status=409)
            artifact = _visible_artifact(request, journey, existing.pk)
            return _reply(_serialize(request, journey, artifact, slug=slug))
        try:
            artifact = owner.create_artifact(
                journey=journey, uploaded_file=uploaded,
                uploaded_by=request.user, kind=kind,
                title=title, step=step, sensitivity=sensitivity,
            )
        except DomainPermissionDenied:
            raise NotFound() from None
        except DomainValidationError as exc:
            raise ValidationError(getattr(exc, "message_dict", None) or exc.messages) from exc
        except IntegrityError:
            existing = JourneyArtifact.objects.filter(
                journey=journey, kind=kind, title=title, version=1,
                content_hash=content_hash, sensitivity=sensitivity,
            ).first()
            if existing is None:
                return _reply({"code": "artifact_conflict"}, status=409)
            artifact = _visible_artifact(request, journey, existing.pk)
            return _reply(_serialize(request, journey, artifact, slug=slug))
        return _reply(_serialize(request, journey, artifact, slug=slug), status=201)


class JourneyArtifactVersionAPIView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, journey_id, artifact_id, slug=None):
        journey = _journey_for_actor(request, journey_id, slug=slug, write=True)
        artifact = _visible_artifact(request, journey, artifact_id)
        if slug is not None and not can_act_for_space_service_journey(request.user, journey):
            raise NotFound()
        if set(request.data.keys()) - {"file", "sensitivity"}:
            raise ValidationError({"fields": "Champs inconnus."})
        uploaded = request.FILES.get("file")
        sensitivity = request.data.get("sensitivity") or artifact.sensitivity
        if sensitivity not in JourneyArtifactSensitivity.values:
            raise ValidationError({"sensitivity": "Sensibilité invalide."})
        if artifact.kind == JourneyArtifactKind.IDENTITY_DOCUMENT and sensitivity != JourneyArtifactSensitivity.RESTRICTED:
            raise ValidationError({"sensitivity": "Une pièce d’identité doit rester restreinte."})
        if artifact.sensitivity == JourneyArtifactSensitivity.RESTRICTED and sensitivity != JourneyArtifactSensitivity.RESTRICTED:
            raise ValidationError({"sensitivity": "Une version ne peut pas déclasser une pièce restreinte."})
        try:
            _data, _mime, sha256 = owner.validate_artifact_upload(uploaded)
        except DomainValidationError as exc:
            raise ValidationError(getattr(exc, "message_dict", None) or exc.messages) from exc
        existing = JourneyArtifact.objects.filter(supersedes=artifact).first()
        if existing is not None:
            if existing.content_hash != sha256 or existing.sensitivity != sensitivity:
                return _reply({"code": "artifact_version_conflict"}, status=409)
            return _reply(_serialize(request, journey, _visible_artifact(request, journey, existing.pk), slug=slug))
        try:
            successor = owner.create_artifact_version(
                artifact=artifact, uploaded_file=uploaded, uploaded_by=request.user,
                sensitivity=sensitivity,
            )
        except DomainPermissionDenied:
            raise NotFound() from None
        except DomainValidationError as exc:
            raise ValidationError(getattr(exc, "message_dict", None) or exc.messages) from exc
        except IntegrityError:
            return _reply({"code": "artifact_version_conflict"}, status=409)
        return _reply(_serialize(request, journey, successor, slug=slug), status=201)


class JourneyArtifactDownloadAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, journey_id, artifact_id, slug=None):
        journey = _journey_for_actor(request, journey_id, slug=slug)
        artifact = _visible_artifact(request, journey, artifact_id)
        if not _may_download(request, journey, artifact):
            raise NotFound()
        try:
            artifact = owner.artifact_for_download(
                actor=request.user, artifact_id=artifact.pk,
            )
            handle = artifact.file.open("rb")
        except (DomainPermissionDenied, OSError, ValueError):
            raise Http404("Pièce indisponible.") from None
        filename = (
            f"{slugify(artifact.title) or 'piece'}-v{artifact.version}"
            f"{EXTENSION_BY_MIME.get(artifact.mime_type, '')}"
        )
        response = FileResponse(
            handle, as_attachment=True, filename=filename,
            content_type=artifact.mime_type,
        )
        response["Cache-Control"] = "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"
        return response
