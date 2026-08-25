import uuid

from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.text import slugify

from activities.models import (
    ActivityStatus,
    ActivityVisibility,
    OccurrencePlaceRole,
    OccurrenceStatus,
)

from .validators import validate_event_cover


# Event keeps the public vocabulary while Activity owns these generic states.
EventStatus = ActivityStatus
EventVisibility = ActivityVisibility


class VenueKind(models.TextChoices):
    PHYSICAL = "physical", "Présentiel"
    ONLINE = "online", "En ligne"
    HYBRID = "hybrid", "Hybride"


def event_cover_path(instance, filename):
    return f"events/{instance.id}/cover/{filename}"


class EventCategory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=140, unique=True, blank=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "catégorie d’événement"
        verbose_name_plural = "catégories d’événements"

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name)[:120] or "categorie"
            candidate, suffix = base, 2
            while EventCategory.objects.exclude(pk=self.pk).filter(slug=candidate).exists():
                candidate = f"{base[:110]}-{suffix}"
                suffix += 1
            self.slug = candidate
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class EventVenue(models.Model):
    """Event-specific venue presentation layered on top of canonical Place.

    Physical geography is canonical in ``place``. The historical geography
    columns remain temporarily for imported/legacy rows only; new Event flows
    never write them.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=180)
    kind = models.CharField(max_length=20, choices=VenueKind.choices, default=VenueKind.PHYSICAL)
    place = models.ForeignKey("geography.Place", on_delete=models.SET_NULL, related_name="event_venues", null=True, blank=True)
    # Compatibility-only geography. Place is the source of truth.
    address = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=120, blank=True)
    country = models.CharField(max_length=120, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    online_url = models.URLField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name", "id"]
        verbose_name = "lieu d’événement"
        verbose_name_plural = "lieux d’événements"

    def clean(self):
        super().clean()
        errors = {}
        if self.kind in {VenueKind.ONLINE, VenueKind.HYBRID} and not self.online_url:
            errors["online_url"] = "Une URL est requise pour un événement en ligne ou hybride."
        if self.kind in {VenueKind.PHYSICAL, VenueKind.HYBRID} and not self.place_id:
            # Historical rows were backfilled in 0003. New physical venues must
            # always point at Geography instead of writing legacy coordinates.
            errors["place"] = "Un lieu physique ou hybride doit référencer un Place canonique."
        if errors:
            raise ValidationError(errors)

    @property
    def effective_address(self):
        return self.place.address_line if self.place_id else self.address

    @property
    def effective_city(self):
        return self.place.locality if self.place_id else self.city

    @property
    def effective_country(self):
        return self.place.country_code if self.place_id else self.country

    @property
    def effective_latitude(self):
        return self.place.latitude if self.place_id else self.latitude

    @property
    def effective_longitude(self):
        return self.place.longitude if self.place_id else self.longitude

    def __str__(self):
        return f"{self.name} — {self.effective_city}" if self.effective_city else self.name


LEGACY_EVENT_LOOKUPS = {
    "organization": "activity__space",
    "organization_id": "activity__space_id",
    "organizer": "activity__created_by",
    "organizer_id": "activity__created_by_id",
    "title": "activity__title",
    "short_description": "activity__short_description",
    "description": "activity__description",
    "status": "activity__status",
    "visibility": "activity__visibility",
    "start_at": "activity__occurrences__start_at",
    "end_at": "activity__occurrences__end_at",
    "timezone": "activity__occurrences__timezone",
}


def _rewrite_lookup(key):
    for legacy, canonical in LEGACY_EVENT_LOOKUPS.items():
        if key == legacy:
            return canonical
        prefix = f"{legacy}__"
        if key.startswith(prefix):
            return f"{canonical}__{key[len(prefix):]}"
    return key


def _rewrite_q(node):
    if not isinstance(node, Q):
        return node
    rewritten = Q()
    rewritten.connector = node.connector
    rewritten.negated = node.negated
    rewritten.children = [
        (_rewrite_lookup(child[0]), child[1]) if isinstance(child, tuple) else _rewrite_q(child)
        for child in node.children
    ]
    return rewritten


class EventQuerySet(models.QuerySet):
    """Compatibility bridge for historical Event queryset vocabulary.

    It rewrites generic Event lookups to canonical relations. New Events code
    uses explicit ``activity__...`` paths; this bridge exists only so older
    consumers do not become a second source of truth during the cutover.
    """

    def _rewrite(self, args, kwargs):
        return tuple(_rewrite_q(arg) for arg in args), {_rewrite_lookup(k): v for k, v in kwargs.items()}

    def filter(self, *args, **kwargs):
        args, kwargs = self._rewrite(args, kwargs)
        return super().filter(*args, **kwargs)

    def exclude(self, *args, **kwargs):
        args, kwargs = self._rewrite(args, kwargs)
        return super().exclude(*args, **kwargs)

    def get(self, *args, **kwargs):
        args, kwargs = self._rewrite(args, kwargs)
        return super().get(*args, **kwargs)

    def order_by(self, *field_names):
        rewritten = []
        for field_name in field_names:
            descending = field_name.startswith("-")
            raw = field_name[1:] if descending else field_name
            mapped = _rewrite_lookup(raw)
            rewritten.append(f"-{mapped}" if descending else mapped)
        return super().order_by(*rewritten)

    def select_for_update(self, nowait=False, skip_locked=False, of=(), no_key=False):
        # Event queries often load Activity.space for presentation. Space is
        # nullable on generic Activity, so PostgreSQL cannot FOR UPDATE the
        # nullable side of that outer join. Lock only the vertical Event row
        # unless a caller explicitly requests another lock scope.
        return super().select_for_update(
            nowait=nowait,
            skip_locked=skip_locked,
            of=of or ("self",),
            no_key=no_key,
        )


class EventManager(models.Manager.from_queryset(EventQuerySet)):
    @transaction.atomic
    def create(self, **kwargs):
        """Canonical-first compatibility for historical ``Event.objects.create``.

        Generic Event arguments are consumed to create Activity/Occurrence.
        No generic value is stored on Event itself.
        """
        if kwargs.get("activity") is not None or kwargs.get("activity_id") is not None:
            return super().create(**kwargs)

        from activities.models import Activity, Occurrence, OccurrencePlace
        from authorization.constants import SystemRoleCode
        from authorization.services import grant_activity_role
        from capacity.models import CapacityPool

        organization = kwargs.pop("organization", None)
        organization_id = kwargs.pop("organization_id", None)
        organizer = kwargs.pop("organizer", None)
        organizer_id = kwargs.pop("organizer_id", None)
        title = kwargs.pop("title", None)
        short_description = kwargs.pop("short_description", "")
        description = kwargs.pop("description", "")
        status = kwargs.pop("status", EventStatus.DRAFT)
        visibility = kwargs.pop("visibility", EventVisibility.PUBLIC)
        start_at = kwargs.pop("start_at", None)
        end_at = kwargs.pop("end_at", None)
        event_timezone = kwargs.pop("timezone", "Africa/Lubumbashi")
        legacy_capacity = kwargs.pop("capacity", None)

        if not title:
            raise TypeError("Event.objects.create() exige title ou une Activity existante.")
        if start_at is None:
            raise TypeError("Event.objects.create() exige start_at ou une Activity existante.")

        activity_values = {
            "title": title,
            "short_description": short_description,
            "description": description,
            "status": status,
            "visibility": visibility,
        }
        has_space = organization is not None or organization_id is not None
        if organization is not None:
            activity_values["space"] = organization
        elif organization_id is not None:
            activity_values["space_id"] = organization_id
        if organizer is not None:
            activity_values["created_by"] = organizer
            if not has_space:
                activity_values["owner_profile"] = organizer
        elif organizer_id is not None:
            activity_values["created_by_id"] = organizer_id
            if not has_space:
                activity_values["owner_profile_id"] = organizer_id
        activity = Activity.objects.create(**activity_values)
        if activity.owner_profile_id:
            owner = organizer or activity.owner_profile
            grant_activity_role(
                profile=owner,
                activity=activity,
                role=SystemRoleCode.ACTIVITY_LOCAL_MANAGER,
                granted_by=owner,
                source="event-manager-compatibility",
            )
        occurrence = Occurrence.objects.create(
            activity=activity,
            start_at=start_at,
            end_at=end_at,
            timezone=event_timezone,
            status=_occurrence_status_for_activity(status),
        )
        event = super().create(activity=activity, **kwargs)

        if event.venue_id and event.venue.place_id:
            OccurrencePlace.objects.update_or_create(
                occurrence=occurrence,
                role=OccurrencePlaceRole.PRIMARY,
                defaults={"place": event.venue.place, "position": 0},
            )
        if legacy_capacity is not None:
            CapacityPool.objects.create(
                activity=activity,
                occurrence=occurrence,
                label="Capacité événement",
                total_quantity=legacy_capacity,
                source_key=f"event:{event.pk}:capacity",
            )
        return event


def _occurrence_status_for_activity(status):
    return {
        EventStatus.DRAFT: OccurrenceStatus.DRAFT,
        EventStatus.PUBLISHED: OccurrenceStatus.SCHEDULED,
        EventStatus.CANCELLED: OccurrenceStatus.CANCELLED,
        EventStatus.COMPLETED: OccurrenceStatus.COMPLETED,
        EventStatus.ARCHIVED: OccurrenceStatus.COMPLETED,
    }.get(status, OccurrenceStatus.DRAFT)


class Event(models.Model):
    """Event-specific configuration composed around a canonical Activity."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    activity = models.OneToOneField("activities.Activity", on_delete=models.PROTECT, related_name="event_vertical")
    category = models.ForeignKey(EventCategory, on_delete=models.SET_NULL, related_name="events", null=True, blank=True)
    venue = models.ForeignKey(EventVenue, on_delete=models.SET_NULL, related_name="events", null=True, blank=True)
    # Kept as a stable Event public/API route identifier. Generic Activity slug
    # remains canonical for Activity surfaces.
    slug = models.SlugField(max_length=240, unique=True, blank=True)
    cover_image = models.ImageField(upload_to=event_cover_path, validators=[validate_event_cover], blank=True, null=True)
    # Event-global registration policy. Ticket sale windows are canonical on
    # Offer and are clamped by vertical services when this policy is set.
    registration_start_at = models.DateTimeField(null=True, blank=True)
    registration_end_at = models.DateTimeField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = EventManager()

    class Meta:
        ordering = ["created_at", "id"]
        verbose_name = "événement"
        verbose_name_plural = "événements"
        indexes = [models.Index(fields=["activity", "created_at"], name="events_activity_created_idx")]

    def clean(self):
        super().clean()
        errors = {}
        if self.registration_start_at and self.registration_end_at and self.registration_end_at <= self.registration_start_at:
            errors["registration_end_at"] = "La fin des inscriptions doit être postérieure à leur début."
        occurrence = self.primary_occurrence if self.activity_id else None
        if occurrence and occurrence.end_at:
            if self.registration_end_at and self.registration_end_at > occurrence.end_at:
                errors["registration_end_at"] = "Les inscriptions ne peuvent pas se terminer après l’événement."
            if self.registration_start_at and self.registration_start_at >= occurrence.end_at:
                errors["registration_start_at"] = "Les inscriptions doivent commencer avant la fin de l’événement."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.title)[:200] or "evenement"
            candidate, suffix = base, 2
            while Event.objects.exclude(pk=self.pk).filter(slug=candidate).exists():
                candidate = f"{base[:225]}-{suffix}"
                suffix += 1
            self.slug = candidate
        self.full_clean()
        return super().save(*args, **kwargs)

    @property
    def organization(self):
        return self.activity.space

    @property
    def organization_id(self):
        return self.activity.space_id

    @property
    def organizer(self):
        return self.activity.created_by

    @property
    def organizer_id(self):
        return self.activity.created_by_id

    @property
    def title(self):
        return self.activity.title

    @property
    def display_title(self):
        return self.activity.title

    @property
    def short_description(self):
        return self.activity.short_description

    @property
    def description(self):
        return self.activity.description

    @property
    def status(self):
        return self.activity.status

    @property
    def display_status(self):
        return self.activity.status

    @property
    def visibility(self):
        return self.activity.visibility

    @property
    def primary_occurrence(self):
        if not self.activity_id:
            return None
        prefetched = getattr(self.activity, "_prefetched_objects_cache", {}).get("occurrences")
        if prefetched is not None:
            return sorted(prefetched, key=lambda occurrence: (occurrence.start_at, str(occurrence.pk)))[0] if prefetched else None
        return self.activity.occurrences.order_by("start_at", "id").first()

    @property
    def primary_place(self):
        occurrence = self.primary_occurrence
        if occurrence is None:
            return None
        prefetched = getattr(occurrence, "_prefetched_objects_cache", {}).get("place_links")
        if prefetched is not None:
            links = [link for link in prefetched if link.role == OccurrencePlaceRole.PRIMARY]
            return links[0].place if links else None
        link = occurrence.place_links.select_related("place").filter(role=OccurrencePlaceRole.PRIMARY).order_by("position", "id").first()
        return link.place if link else None

    @property
    def start_at(self):
        occurrence = self.primary_occurrence
        return occurrence.start_at if occurrence else None

    @property
    def end_at(self):
        occurrence = self.primary_occurrence
        return occurrence.end_at if occurrence else None

    @property
    def timezone(self):
        occurrence = self.primary_occurrence
        return occurrence.timezone if occurrence else ""

    @property
    def capacity(self):
        """Readonly compatibility projection; CapacityPool decides availability."""
        occurrence = self.primary_occurrence
        if occurrence is None:
            return None
        pool = self.activity.capacity_pools.filter(
            occurrence=occurrence,
            is_active=True,
            source_key=f"event:{self.pk}:capacity",
        ).first()
        return pool.total_quantity if pool else None

    @property
    def is_upcoming(self):
        return bool(self.start_at and self.start_at > timezone.now())

    @property
    def is_registration_open(self):
        now = timezone.now()
        if self.status != EventStatus.PUBLISHED:
            return False
        if self.registration_start_at and now < self.registration_start_at:
            return False
        if self.registration_end_at and now >= self.registration_end_at:
            return False
        return bool(self.end_at and now < self.end_at)

    def __str__(self):
        return self.title