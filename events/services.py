from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from activities.models import ActivityStatus, OccurrencePlace, OccurrencePlaceRole, OccurrenceStatus
from activities.services import (
    attach_occurrence_place,
    complete_occurrence,
    create_activity,
    create_occurrence,
    reopen_completed_activity,
    reopen_completed_occurrence,
    reschedule_occurrence,
    set_occurrence_status,
    update_activity_common,
)
from authorization.constants import PermissionCode
from authorization.services import can
from capacity.models import CapacityPool
from commerce.models import OfferStatus
from commerce.services import update_offer

from .models import Event, EventStatus, VenueKind
from .permissions import user_can_manage_event


UNSET = object()
CORE_ACTIVITY_FIELDS = {"title", "short_description", "description", "visibility"}
CORE_OCCURRENCE_FIELDS = {"start_at", "end_at", "timezone"}
EVENT_FIELDS = {
    "category",
    "venue",
    "cover_image",
    "registration_start_at",
    "registration_end_at",
    "metadata",
}
COMPLETED_EVENT_LOCKED_FIELDS = {
    "venue",
    "start_at",
    "end_at",
    "timezone",
    "registration_start_at",
    "registration_end_at",
    "capacity",
}


def _ensure_can_manage(actor, event: Event) -> None:
    if not user_can_manage_event(actor, event):
        raise PermissionDenied("Vous ne pouvez pas gérer cet événement.")


def _ensure_can_create(actor, space=None) -> None:
    if not getattr(actor, "is_authenticated", False):
        raise PermissionDenied("Authentification requise.")
    if space is not None and not can(actor, PermissionCode.SPACE_ACTIVITIES_MANAGE, space):
        raise PermissionDenied("Vous ne pouvez pas créer d’événement dans cet Espace.")


def _set_primary_place(*, event, occurrence):
    venue = event.venue
    if venue and venue.kind in {VenueKind.PHYSICAL, VenueKind.HYBRID}:
        if not venue.place_id:
            raise ValidationError({"venue": "Le lieu physique doit référencer un Place canonique."})
        return attach_occurrence_place(
            occurrence=occurrence,
            place=venue.place,
            role=OccurrencePlaceRole.PRIMARY,
            position=0,
        )
    OccurrencePlace.objects.filter(
        occurrence=occurrence,
        role=OccurrencePlaceRole.PRIMARY,
    ).delete()
    return None


def _set_event_capacity(*, event, occurrence, total_quantity):
    """Compatibility Event quota backed by one canonical CapacityPool."""
    source_key = f"event:{event.pk}:capacity"
    pool = CapacityPool.objects.select_for_update().filter(source_key=source_key).first()
    if pool is None:
        if total_quantity is None:
            return None
        pool = CapacityPool(
            activity=event.activity,
            occurrence=occurrence,
            label="Capacité événement",
            total_quantity=total_quantity,
            source_key=source_key,
        )
        pool.save()
        return pool
    pool.activity = event.activity
    pool.occurrence = occurrence
    pool.total_quantity = total_quantity
    pool.is_active = True
    pool.save(update_fields=["activity", "occurrence", "total_quantity", "is_active", "updated_at"])
    return pool


def _clamp_offer_windows(event):
    """Apply Event-global registration bounds without replacing Offer policy."""
    for offer in event.activity.offers.select_for_update().all():
        values = {}
        if event.registration_start_at and (
            offer.available_from is None or offer.available_from < event.registration_start_at
        ):
            values["available_from"] = event.registration_start_at
        if event.registration_end_at and (
            offer.available_until is None or offer.available_until > event.registration_end_at
        ):
            values["available_until"] = event.registration_end_at
        if values:
            update_offer(offer=offer, **values)


def _event_specific_values(fields):
    return {name: fields[name] for name in EVENT_FIELDS if name in fields}


@transaction.atomic
def create_event(
    *,
    actor,
    title,
    start_at,
    end_at,
    organization=None,
    timezone="Africa/Lubumbashi",
    short_description="",
    description="",
    visibility="public",
    category=None,
    venue=None,
    cover_image=None,
    registration_start_at=None,
    registration_end_at=None,
    metadata=None,
    capacity=UNSET,
) -> Event:
    """Create an Event as a vertical over one explicitly-owned Activity."""
    _ensure_can_create(actor, organization)
    activity = create_activity(
        space=organization,
        owner_profile=actor if organization is None else None,
        created_by=actor,
        title=title,
        short_description=short_description,
        description=description,
        visibility=visibility,
        status=ActivityStatus.DRAFT,
    )
    occurrence = create_occurrence(
        activity=activity,
        start_at=start_at,
        end_at=end_at,
        timezone=timezone,
        status=OccurrenceStatus.DRAFT,
    )
    event = Event(
        activity=activity,
        category=category,
        venue=venue,
        cover_image=cover_image,
        registration_start_at=registration_start_at,
        registration_end_at=registration_end_at,
        metadata=metadata or {},
    )
    event.full_clean()
    event.save()
    _set_primary_place(event=event, occurrence=occurrence)
    if capacity is not UNSET:
        _set_event_capacity(event=event, occurrence=occurrence, total_quantity=capacity)
    return event


@transaction.atomic
def update_event(*, event: Event, actor, organization=None, **fields) -> Event:
    """Route each Event form value to its canonical owner."""
    _ensure_can_manage(actor, event)
    activity = event.activity
    occurrence = event.primary_occurrence
    if occurrence is None:
        raise ValidationError("Cet événement ne possède pas de date principale.")

    if event.status == EventStatus.COMPLETED:
        locked = COMPLETED_EVENT_LOCKED_FIELDS & fields.keys()
        if locked:
            raise ValidationError(
                "La date, le lieu, les inscriptions et la capacité d’un événement terminé restent verrouillés. "
                "Réouvrez l’événement seulement si sa clôture était une erreur."
            )
        if organization is not None and organization.pk != activity.space_id:
            raise ValidationError(
                "Un événement terminé ne peut pas être déplacé vers un autre Espace."
            )

    activity_values = {name: fields[name] for name in CORE_ACTIVITY_FIELDS if name in fields}
    if organization is not None and organization.pk != activity.space_id:
        if activity.owner_profile_id:
            raise ValidationError(
                "Le transfert d’une Activity personnelle vers un Espace n’est pas réalisé depuis ce formulaire."
            )
        if not can(actor, PermissionCode.SPACE_ACTIVITIES_MANAGE, organization):
            raise PermissionDenied("Vous ne pouvez pas déplacer cet événement vers cet Espace.")
        activity_values["space"] = organization
    if activity_values:
        update_activity_common(activity=activity, **activity_values)

    if CORE_OCCURRENCE_FIELDS & fields.keys():
        reschedule_occurrence(
            occurrence=occurrence,
            start_at=fields.get("start_at", occurrence.start_at),
            end_at=fields.get("end_at", occurrence.end_at),
            timezone=fields.get("timezone", occurrence.timezone),
        )

    event_values = _event_specific_values(fields)
    if "cover_image" in event_values and not event_values["cover_image"]:
        event_values.pop("cover_image")
    for name, value in event_values.items():
        setattr(event, name, value)
    event.full_clean()
    if event_values:
        event.save(update_fields=[*event_values.keys(), "updated_at"])
    else:
        event.save(update_fields=["updated_at"])

    if "venue" in fields:
        _set_primary_place(event=event, occurrence=occurrence)
    if "capacity" in fields:
        _set_event_capacity(event=event, occurrence=occurrence, total_quantity=fields["capacity"])
    if {"registration_start_at", "registration_end_at"} & fields.keys():
        _clamp_offer_windows(event)
    return event


@transaction.atomic
def publish_event(*, event: Event, actor) -> Event:
    _ensure_can_manage(actor, event)
    occurrence = event.primary_occurrence
    if event.status != EventStatus.DRAFT:
        raise ValidationError("Seul un brouillon peut être publié.")
    if occurrence is None or occurrence.end_at is None or occurrence.end_at <= timezone.now():
        raise ValidationError("Un événement déjà terminé ne peut pas être publié.")
    event.full_clean()
    _clamp_offer_windows(event)
    update_activity_common(activity=event.activity, status=ActivityStatus.PUBLISHED)
    set_occurrence_status(occurrence=occurrence, status=OccurrenceStatus.SCHEDULED)
    for offer in event.activity.offers.select_for_update().filter(status=OfferStatus.DRAFT):
        update_offer(offer=offer, status=OfferStatus.ACTIVE)
    event.published_at = timezone.now()
    event.cancelled_at = None
    event.save(update_fields=["published_at", "cancelled_at", "updated_at"])
    return event


@transaction.atomic
def cancel_event(*, event: Event, actor) -> Event:
    _ensure_can_manage(actor, event)
    if event.status not in {EventStatus.DRAFT, EventStatus.PUBLISHED}:
        raise ValidationError("Seul un brouillon ou un événement publié peut être annulé.")
    occurrence = event.primary_occurrence
    update_activity_common(activity=event.activity, status=ActivityStatus.CANCELLED)
    if occurrence is not None:
        set_occurrence_status(occurrence=occurrence, status=OccurrenceStatus.CANCELLED)
    event.cancelled_at = timezone.now()
    event.save(update_fields=["cancelled_at", "updated_at"])
    return event


@transaction.atomic
def complete_event(*, event: Event, actor) -> Event:
    _ensure_can_manage(actor, event)
    if event.status != EventStatus.PUBLISHED:
        raise ValidationError("Seul un événement publié peut être terminé.")
    occurrence = event.primary_occurrence
    update_activity_common(activity=event.activity, status=ActivityStatus.COMPLETED)
    if occurrence is not None:
        complete_occurrence(occurrence=occurrence)
    event.save(update_fields=["updated_at"])
    return event


@transaction.atomic
def reopen_event(*, event: Event, actor) -> Event:
    """Undo an erroneous early completion without creating a new session."""
    _ensure_can_manage(actor, event)
    event = Event.objects.select_for_update().select_related("activity").get(pk=event.pk)
    occurrence = event.primary_occurrence
    if event.status != EventStatus.COMPLETED:
        raise ValidationError("Seul un événement terminé peut être réouvert.")
    if occurrence is None or occurrence.status != OccurrenceStatus.COMPLETED:
        raise ValidationError("La date de cet événement n’est pas dans un état réouvrable.")
    if occurrence.end_at is None or occurrence.end_at <= timezone.now():
        raise ValidationError(
            "Cette date est réellement passée. Créez une nouvelle date ou session au lieu de réouvrir l’historique."
        )

    before = {
        "status": event.status,
        "occurrence_status": occurrence.status,
    }
    reopen_completed_activity(activity=event.activity)
    reopen_completed_occurrence(occurrence=occurrence)
    event.save(update_fields=["updated_at"])

    # OperationsAuditLog is the existing explicit audit ledger. Import lazily
    # to avoid coupling the Event module's import graph to Operations views.
    from operations.services import audit_action

    audit_action(
        actor=actor,
        action="event.reopened",
        target_type="event",
        target_id=event.pk,
        summary=f"Réouverture de {event.title} après une clôture prématurée.",
        before=before,
        after={
            "status": event.status,
            "occurrence_status": occurrence.status,
        },
        metadata={
            "activity_id": str(event.activity_id),
            "occurrence_id": str(occurrence.pk),
        },
    )
    return event
