from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from authorization.constants import PermissionCode
from authorization.services import can
from domain_events.contracts import DomainEventType
from domain_events.services import emit_domain_event

from .models import Dossier, DossierJourneyLink, DossierLifecycle


ALLOWED_LIFECYCLE_TRANSITIONS = {
    DossierLifecycle.DRAFT: {DossierLifecycle.ACTIVE, DossierLifecycle.CANCELLED, DossierLifecycle.ARCHIVED},
    DossierLifecycle.ACTIVE: {DossierLifecycle.COMPLETED, DossierLifecycle.CANCELLED, DossierLifecycle.ARCHIVED},
    DossierLifecycle.COMPLETED: {DossierLifecycle.ARCHIVED},
    DossierLifecycle.CANCELLED: {DossierLifecycle.ARCHIVED},
    DossierLifecycle.ARCHIVED: set(),
}


def _require_authenticated(actor):
    if not getattr(actor, "is_authenticated", False):
        raise PermissionDenied("Authentification requise.")


def can_view_dossier(actor, dossier):
    if not getattr(actor, "is_authenticated", False):
        return False
    if can(actor, PermissionCode.PLATFORM_MANAGE):
        return True
    if dossier.owner_profile_id:
        return dossier.owner_profile_id == actor.pk
    return can(actor, PermissionCode.SPACE_VIEW, space=dossier.owning_space) or can(
        actor, PermissionCode.SPACE_MANAGE, space=dossier.owning_space
    )


def can_manage_dossier(actor, dossier):
    if not getattr(actor, "is_authenticated", False):
        return False
    if can(actor, PermissionCode.PLATFORM_MANAGE):
        return True
    if dossier.owner_profile_id:
        return dossier.owner_profile_id == actor.pk
    return can(actor, PermissionCode.SPACE_MANAGE, space=dossier.owning_space)


def can_use_journey_for_dossier(actor, journey):
    if not getattr(actor, "is_authenticated", False):
        return False
    if journey.beneficiary_id == actor.pk or journey.initiated_by_id == actor.pk:
        return True
    return can(actor, PermissionCode.ACTIVITY_REQUESTS_VIEW, activity=journey.activity)


def _emit(*, event_type, dossier, idempotency_key, payload):
    return emit_domain_event(
        event_type=event_type,
        source_type="objectives.Dossier",
        source_id=dossier.pk,
        idempotency_key=idempotency_key,
        space_id=dossier.owning_space_id,
        payload=payload,
    )


@transaction.atomic
def create_dossier(*, actor, title, description="", owner_profile=None, owning_space=None, deadline=None):
    _require_authenticated(actor)
    if bool(owner_profile) == bool(owning_space):
        raise ValidationError("Choisissez exactement un porteur personnel ou Espace.")
    if owner_profile is not None:
        if owner_profile.pk != actor.pk and not can(actor, PermissionCode.PLATFORM_MANAGE):
            raise PermissionDenied("Un Dossier personnel doit être créé pour soi-même.")
    elif not can(actor, PermissionCode.SPACE_MANAGE, space=owning_space):
        raise PermissionDenied("Autorité de gestion de l’Espace requise.")
    dossier = Dossier(
        title=title,
        description=description,
        created_by=actor,
        owner_profile=owner_profile,
        owning_space=owning_space,
        deadline=deadline,
    )
    dossier.save()
    _emit(
        event_type=DomainEventType.DOSSIER_CREATED,
        dossier=dossier,
        idempotency_key=f"dossier:{dossier.pk}:created",
        payload={"dossier_id": str(dossier.pk), "owning_space_id": str(dossier.owning_space_id or "")},
    )
    return dossier


@transaction.atomic
def link_journey(*, actor, dossier, journey):
    _require_authenticated(actor)
    dossier = Dossier.objects.select_for_update().select_related("owner_profile", "owning_space").get(pk=dossier.pk)
    if not can_manage_dossier(actor, dossier):
        raise PermissionDenied("Autorité de gestion du Dossier requise.")
    if not can_use_journey_for_dossier(actor, journey):
        raise PermissionDenied("Cette démarche n’est pas autorisée dans ce contexte.")
    existing = (
        DossierJourneyLink.objects.select_for_update()
        .filter(dossier=dossier, journey=journey, is_active=True)
        .first()
    )
    if existing:
        return existing
    link = DossierJourneyLink.objects.create(dossier=dossier, journey=journey, linked_by=actor)
    _emit(
        event_type=DomainEventType.DOSSIER_JOURNEY_LINKED,
        dossier=dossier,
        idempotency_key=f"dossier-link:{link.pk}:linked",
        payload={"dossier_id": str(dossier.pk), "journey_id": str(journey.pk)},
    )
    return link


@transaction.atomic
def unlink_journey(*, actor, dossier, journey):
    _require_authenticated(actor)
    dossier = Dossier.objects.select_for_update().select_related("owner_profile", "owning_space").get(pk=dossier.pk)
    if not can_manage_dossier(actor, dossier):
        raise PermissionDenied("Autorité de gestion du Dossier requise.")
    if not can_use_journey_for_dossier(actor, journey):
        raise PermissionDenied("Cette démarche n’est pas autorisée dans ce contexte.")
    link = (
        DossierJourneyLink.objects.select_for_update()
        .filter(dossier=dossier, journey=journey, is_active=True)
        .first()
    )
    if link is None:
        return DossierJourneyLink.objects.filter(dossier=dossier, journey=journey).order_by("-linked_at").first()
    link.is_active = False
    link.unlinked_by = actor
    link.unlinked_at = timezone.now()
    link.save(update_fields=["is_active", "unlinked_by", "unlinked_at"])
    _emit(
        event_type=DomainEventType.DOSSIER_JOURNEY_UNLINKED,
        dossier=dossier,
        idempotency_key=f"dossier-link:{link.pk}:unlinked",
        payload={"dossier_id": str(dossier.pk), "journey_id": str(journey.pk)},
    )
    return link


@transaction.atomic
def set_dossier_lifecycle(*, actor, dossier, lifecycle):
    _require_authenticated(actor)
    dossier = Dossier.objects.select_for_update().select_related("owner_profile", "owning_space").get(pk=dossier.pk)
    if not can_manage_dossier(actor, dossier):
        raise PermissionDenied("Autorité de gestion du Dossier requise.")
    lifecycle = str(lifecycle)
    if lifecycle not in DossierLifecycle.values:
        raise ValidationError("Lifecycle Dossier inconnu.")
    previous = dossier.lifecycle
    if previous == lifecycle:
        return dossier
    if lifecycle not in ALLOWED_LIFECYCLE_TRANSITIONS[previous]:
        raise ValidationError(f"Transition Dossier interdite: {previous} → {lifecycle}.")
    dossier.lifecycle = lifecycle
    dossier._allow_lifecycle_transition = True
    dossier.save(update_fields=["lifecycle", "updated_at"])
    _emit(
        event_type=DomainEventType.DOSSIER_LIFECYCLE_CHANGED,
        dossier=dossier,
        idempotency_key=f"dossier:{dossier.pk}:lifecycle:{previous}:{lifecycle}:{dossier.updated_at.isoformat()}",
        payload={"dossier_id": str(dossier.pk), "previous": previous, "current": lifecycle},
    )
    return dossier
