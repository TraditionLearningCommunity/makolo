from __future__ import annotations

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from authorization.constants import PermissionCode
from authorization.services import can
from domain_events.contracts import DomainEventType
from domain_events.services import emit_domain_event
from journeys.models import Journey

from .models import ActivityResource, ResourceStatus, ResourceVisibility


def _require_manage(actor, activity):
    if not getattr(actor, "is_authenticated", False) or not can(actor, PermissionCode.ACTIVITY_MANAGE, activity=activity):
        raise PermissionDenied("La gestion des Resources de cette Activity n’est pas autorisée.")


def can_view_resource(actor, resource):
    if resource.status != ResourceStatus.PUBLISHED:
        return bool(getattr(actor, "is_authenticated", False) and can(actor, PermissionCode.ACTIVITY_MANAGE, activity=resource.activity))
    if resource.visibility == ResourceVisibility.PUBLIC:
        return True
    if not getattr(actor, "is_authenticated", False):
        return False
    if resource.visibility == ResourceVisibility.RESTRICTED:
        return can(actor, PermissionCode.ACTIVITY_MANAGE, activity=resource.activity)
    return Journey.objects.filter(
        activity=resource.activity,
        beneficiary=actor,
    ).exclude(status__in=["rejected", "cancelled", "expired"]).filter(
        occurrence_id=resource.occurrence_id if resource.occurrence_id else models_f("occurrence_id")
    ).exists() if resource.occurrence_id else Journey.objects.filter(
        activity=resource.activity,
        beneficiary=actor,
    ).exclude(status__in=["rejected", "cancelled", "expired"]).exists()


def models_f(field):
    from django.db.models import F
    return F(field)


def resources_for_actor(*, actor, activity, occurrence=None):
    queryset = ActivityResource.objects.filter(activity=activity, status=ResourceStatus.PUBLISHED).select_related("activity", "occurrence")
    if occurrence is not None:
        queryset = queryset.filter(models_q_occurrence(occurrence))
    allowed = []
    for resource in queryset:
        if can_view_resource(actor, resource):
            allowed.append(resource)
    return allowed


def models_q_occurrence(occurrence):
    from django.db.models import Q
    return Q(occurrence__isnull=True) | Q(occurrence=occurrence)


def _emit(event_type, resource, suffix):
    return emit_domain_event(
        event_type=event_type,
        source_type="activity_resource",
        source_id=resource.pk,
        idempotency_key=f"activity_resource:{resource.pk}:{suffix}",
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
def replace_resource(*, resource, actor, **changes):
    _require_manage(actor, resource.activity)
    resource = ActivityResource.objects.select_for_update().select_related("activity", "occurrence").get(pk=resource.pk)
    if resource.status != ResourceStatus.PUBLISHED:
        raise ValidationError("Seule une Resource publiée peut être remplacée.")
    allowed = {
        "title", "description", "kind", "text_content", "external_url", "file", "mime_type", "size", "content_hash", "visibility", "significant_update"
    }
    data = {field: getattr(resource, field) for field in allowed}
    data.update({key: value for key, value in changes.items() if key in allowed})
    replacement = ActivityResource.objects.create(
        activity=resource.activity,
        occurrence=resource.occurrence,
        key=resource.key,
        version=resource.version + 1,
        supersedes=resource,
        created_by=actor,
        **data,
    )
    replacement.status = ResourceStatus.PUBLISHED
    replacement.published_at = timezone.now()
    replacement._allow_status_transition = True
    replacement.save(update_fields=["status", "published_at", "updated_at"])
    resource.status = ResourceStatus.SUPERSEDED
    resource._allow_status_transition = True
    resource.save(update_fields=["status", "updated_at"])
    _emit(DomainEventType.RESOURCE_REPLACED, replacement, f"replaced:{resource.pk}")
    return replacement
