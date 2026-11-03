from __future__ import annotations

import hashlib

from django.conf import settings

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from authorization.constants import PermissionCode
from authorization.services import can
from domain_events.contracts import DomainEventType
from domain_events.services import emit_domain_event
from journeys.collaboration_services import validate_artifact_upload
from journeys.models import Journey

from .models import ActivityResource, ResourceKind, ResourceStatus, ResourceVisibility


TERMINAL_UNSUCCESSFUL_JOURNEY_STATUSES = {"rejected", "cancelled", "expired"}


def _validate_resource_upload(uploaded_file):
    """Signature-check documentary CSV, MP4 and WAV without relaxing Journey."""
    mime = (getattr(uploaded_file, "content_type", "") or "").split(";", 1)[0].strip().lower()
    if mime not in {"text/csv", "video/mp4", "audio/wav"}:
        return validate_artifact_upload(uploaded_file)
    limit = int(getattr(settings, "DATA_UPLOAD_MAX_MEMORY_SIZE", 12 * 1024 * 1024))
    size = int(getattr(uploaded_file, "size", 0) or 0)
    if not 0 < size <= limit:
        raise ValidationError("Fichier documentaire vide ou trop volumineux.")
    uploaded_file.seek(0)
    data = uploaded_file.read(limit + 1)
    uploaded_file.seek(0)
    if len(data) != size:
        raise ValidationError("Taille du fichier documentaire incorrecte.")
    if mime == "text/csv":
        try:
            text = data.decode("utf-8-sig")
            valid = not any(ord(char) == 0 for char in text) and (
                "\n" in text or "," in text or ";" in text
            )
        except UnicodeDecodeError:
            valid = False
    elif mime == "video/mp4":
        valid = len(data) > 16 and data[4:8] == b"ftyp"
    else:
        valid = len(data) > 44 and data[:4] == b"RIFF" and data[8:12] == b"WAVE"
    if not valid:
        raise ValidationError("Signature de fichier documentaire invalide.")
    return data, mime, hashlib.sha256(data).hexdigest()


def _require_manage(actor, activity):
    if not getattr(actor, "is_authenticated", False) or not can(actor, PermissionCode.ACTIVITY_MANAGE, activity=activity):
        raise PermissionDenied("La gestion des Resources de cette Activity n’est pas autorisée.")


def _participant_has_context(actor, resource):
    queryset = Journey.objects.filter(activity=resource.activity, beneficiary=actor).exclude(
        status__in=TERMINAL_UNSUCCESSFUL_JOURNEY_STATUSES
    )
    if resource.occurrence_id:
        queryset = queryset.filter(occurrence_id=resource.occurrence_id)
    return queryset.exists()


def _public_activity_resource_allowed(actor, activity):
    """Published public Resource != authority to reveal a private Activity."""
    from accounts.models import UserProfile
    from activities.models import ActivityStatus, ActivityVisibility
    from groups.selectors import eligible_activity_ids_for_profile
    from organizations.models import SpaceLifecycle

    if (
        activity.status != ActivityStatus.PUBLISHED
        or activity.visibility != ActivityVisibility.PUBLIC
        or activity.pk not in eligible_activity_ids_for_profile(actor, [activity.pk])
    ):
        return False
    if activity.space_id:
        space = activity.space
        return bool(
            space.public_profile and space.searchable
            and space.lifecycle == SpaceLifecycle.ACTIVE
            and space.verification_status != "suspended"
        )
    return UserProfile.objects.filter(
        user_id=activity.owner_profile_id,
        public_profile=True,
        searchable=True,
        user__is_active=True,
    ).exists()


def can_view_resource(actor, resource):
    if resource.status != ResourceStatus.PUBLISHED:
        return bool(getattr(actor, "is_authenticated", False) and can(actor, PermissionCode.ACTIVITY_MANAGE, activity=resource.activity))
    if resource.visibility == ResourceVisibility.PUBLIC:
        if _public_activity_resource_allowed(actor, resource.activity):
            return True
        if getattr(actor, "is_authenticated", False):
            return (
                can(actor, PermissionCode.ACTIVITY_MANAGE, activity=resource.activity)
                or _participant_has_context(actor, resource)
            )
        return False
    if not getattr(actor, "is_authenticated", False):
        return False
    if resource.visibility == ResourceVisibility.RESTRICTED:
        return can(actor, PermissionCode.ACTIVITY_MANAGE, activity=resource.activity)
    return _participant_has_context(actor, resource)


def resources_for_journey(*, journey, actor):
    is_beneficiary = getattr(actor, "is_authenticated", False) and journey.beneficiary_id == actor.pk
    is_manager = getattr(actor, "is_authenticated", False) and can(actor, PermissionCode.ACTIVITY_MANAGE, activity=journey.activity)
    if not is_beneficiary and not is_manager:
        raise PermissionDenied("Accès refusé aux Resources de cette Journey.")
    visibility = [ResourceVisibility.PUBLIC, ResourceVisibility.PARTICIPANT]
    if is_manager:
        visibility.append(ResourceVisibility.RESTRICTED)
    return list(
        ActivityResource.objects.filter(
            activity=journey.activity,
            status=ResourceStatus.PUBLISHED,
            visibility__in=visibility,
        )
        .filter(Q(occurrence__isnull=True) | Q(occurrence=journey.occurrence))
        .select_related("activity", "occurrence")
        .order_by("title", "version", "id")
    )


def _emit(event_type, resource, suffix):
    return emit_domain_event(
        event_type=event_type,
        source_type="activity_resource",
        source_id=resource.pk,
        idempotency_key=f"activity_resource:{resource.pk}:{suffix}"[:255],
        payload={
            "resource_id": str(resource.pk),
            "activity_id": str(resource.activity_id),
            "occurrence_id": str(resource.occurrence_id) if resource.occurrence_id else None,
            "significant_update": bool(resource.significant_update),
        },
        space_id=resource.activity.space_id,
        activity_id=resource.activity_id,
    )


@transaction.atomic
def create_resource(
    *,
    activity,
    actor,
    key,
    title,
    kind,
    occurrence=None,
    description="",
    text_content="",
    external_url="",
    uploaded_file=None,
    visibility=ResourceVisibility.PARTICIPANT,
    significant_update=False,
):
    _require_manage(actor, activity)
    if occurrence is not None and occurrence.activity_id != activity.pk:
        raise ValidationError("L’Occurrence doit appartenir à l’Activity.")
    resource = ActivityResource(
        activity=activity,
        occurrence=occurrence,
        key=key,
        title=(title or "").strip(),
        description=(description or "").strip(),
        kind=kind,
        text_content=text_content if kind == ResourceKind.TEXT else "",
        external_url=external_url if kind == ResourceKind.URL else "",
        visibility=visibility,
        significant_update=bool(significant_update),
        created_by=actor,
    )
    if kind == ResourceKind.FILE:
        data, mime_type, content_hash = _validate_resource_upload(uploaded_file)
        resource.size = len(data)
        resource.mime_type = mime_type
        resource.content_hash = content_hash
        resource.file.save("resource.bin", ContentFile(data), save=False)
    try:
        resource.save()
    except Exception:
        if resource.file and resource.file.name:
            resource.file.storage.delete(resource.file.name)
        raise
    return resource


@transaction.atomic
def publish_resource(*, resource, actor):
    _require_manage(actor, resource.activity)
    resource = ActivityResource.objects.select_for_update().select_related("activity").get(pk=resource.pk)
    if resource.status != ResourceStatus.DRAFT:
        raise ValidationError("Seule une Resource brouillon peut être publiée.")
    resource.status = ResourceStatus.PUBLISHED
    resource.published_at = timezone.now()
    resource._allow_status_transition = True
    resource.save(update_fields=["status", "published_at", "updated_at"])
    _emit(DomainEventType.RESOURCE_PUBLISHED, resource, "published")
    return resource


@transaction.atomic
def replace_resource(*, resource, actor, uploaded_file=None, **changes):
    _require_manage(actor, resource.activity)
    resource = ActivityResource.objects.select_for_update().select_related("activity", "occurrence").get(pk=resource.pk)
    if resource.status != ResourceStatus.PUBLISHED:
        raise ValidationError("Seule une Resource publiée peut être remplacée.")
    allowed = {"title", "description", "kind", "text_content", "external_url", "visibility", "significant_update"}
    data = {field: getattr(resource, field) for field in allowed}
    data.update({key: value for key, value in changes.items() if key in allowed})
    replacement = ActivityResource(
        activity=resource.activity,
        occurrence=resource.occurrence,
        key=resource.key,
        version=resource.version + 1,
        supersedes=resource,
        created_by=actor,
        **data,
    )
    if replacement.kind == ResourceKind.FILE:
        if uploaded_file is None:
            raise ValidationError("Une nouvelle version de fichier exige un nouveau fichier.")
        file_data, mime_type, content_hash = _validate_resource_upload(uploaded_file)
        replacement.size = len(file_data)
        replacement.mime_type = mime_type
        replacement.content_hash = content_hash
        replacement.file.save("resource.bin", ContentFile(file_data), save=False)
    try:
        replacement.save()
    except Exception:
        if replacement.file and replacement.file.name:
            replacement.file.storage.delete(replacement.file.name)
        raise
    replacement.status = ResourceStatus.PUBLISHED
    replacement.published_at = timezone.now()
    replacement._allow_status_transition = True
    replacement.save(update_fields=["status", "published_at", "updated_at"])
    resource.status = ResourceStatus.SUPERSEDED
    resource._allow_status_transition = True
    resource.save(update_fields=["status", "updated_at"])
    _emit(DomainEventType.RESOURCE_REPLACED, replacement, f"replaced:{resource.pk}")
    return replacement


@transaction.atomic
def retire_resource(*, resource, actor):
    """Retire a published Resource without deleting its versions or stored bytes."""
    _require_manage(actor, resource.activity)
    current = ActivityResource.objects.select_for_update().select_related("activity").get(pk=resource.pk)
    _require_manage(actor, current.activity)
    if current.status != ResourceStatus.PUBLISHED:
        raise ValidationError("Seule une Resource publiée peut être retirée.")
    current.status = ResourceStatus.RETIRED
    current._allow_status_transition = True
    current.save(update_fields=["status", "updated_at"])
    _emit(DomainEventType.RESOURCE_RETIRED, current, "retired")
    return current
