from __future__ import annotations

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


def can_view_resource(actor, resource):
    if resource.status != ResourceStatus.PUBLISHED:
        return bool(getattr(actor, "is_authenticated", False) and can(actor, PermissionCode.ACTIVITY_MANAGE, activity=resource.activity))
    if resource.visibility == ResourceVisibility.PUBLIC:
        return True
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
        data, mime_type, content_hash = validate_artifact_upload(uploaded_file)
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
        file_data, mime_type, content_hash = validate_artifact_upload(uploaded_file)
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
