import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.utils.text import slugify

from geography.validators import validate_timezone_name


class ActivityStatus(models.TextChoices):
    DRAFT = "draft", "Brouillon"
    PUBLISHED = "published", "Publiée"
    CANCELLED = "cancelled", "Annulée"
    COMPLETED = "completed", "Terminée"
    ARCHIVED = "archived", "Archivée"


class ActivityVisibility(models.TextChoices):
    PUBLIC = "public", "Public"
    UNLISTED = "unlisted", "Non répertoriée"
    PRIVATE = "private", "Privée"


class Activity(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    space = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="activities",
        null=True,
        blank=True,
    )
    owner_profile = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="owned_activities",
        null=True,
        blank=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_activities",
        null=True,
        blank=True,
    )
    title = models.CharField(max_length=220)
    slug = models.SlugField(max_length=240, blank=True)
    short_description = models.CharField(max_length=320, blank=True)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=ActivityStatus.choices, default=ActivityStatus.DRAFT)
    visibility = models.CharField(max_length=20, choices=ActivityVisibility.choices, default=ActivityVisibility.PUBLIC)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["title", "id"]
        constraints = [
            models.CheckConstraint(
                condition=~Q(space__isnull=False, owner_profile__isnull=False),
                name="activities_single_logical_owner",
            ),
            models.UniqueConstraint(
                fields=["space", "slug"],
                condition=Q(space__isnull=False),
                name="activities_space_slug_unique",
            ),
            models.UniqueConstraint(
                fields=["owner_profile", "slug"],
                condition=Q(owner_profile__isnull=False, space__isnull=True),
                name="activities_profile_slug_unique",
            ),
            # Compatibility only for pre-T24 rows whose logical owner cannot be
            # inferred safely. New rows are rejected by clean() if both owners
            # are absent.
            models.UniqueConstraint(
                fields=["slug"],
                condition=Q(space__isnull=True, owner_profile__isnull=True),
                name="activities_legacy_slug_unique",
            ),
        ]
        indexes = [
            models.Index(fields=["space", "status"], name="activities_space_status_idx"),
            models.Index(fields=["owner_profile", "status"], name="activities_owner_status_idx"),
            models.Index(fields=["visibility", "status"], name="activities_visibility_idx"),
        ]

    def clean(self):
        super().clean()
        if self.space_id and self.owner_profile_id:
            raise ValidationError(
                "Une Activity appartient soit à un Profil, soit à un Espace, jamais aux deux."
            )
        if not self.space_id and not self.owner_profile_id and self._state.adding:
            raise ValidationError(
                "Toute nouvelle Activity doit avoir un propriétaire logique explicite."
            )

    def _slug_scope(self):
        queryset = Activity.objects.exclude(pk=self.pk)
        if self.space_id:
            return queryset.filter(space_id=self.space_id)
        if self.owner_profile_id:
            return queryset.filter(space_id=None, owner_profile_id=self.owner_profile_id)
        return queryset.filter(space_id=None, owner_profile_id=None)

    @property
    def is_personal(self):
        return bool(self.owner_profile_id and not self.space_id)

    @property
    def operator_display_name(self):
        if self.space_id:
            return self.space.name
        if self.owner_profile_id:
            return self.owner_profile.full_name or self.owner_profile.username
        # Legacy compatibility only. created_by remains provenance and is not
        # promoted to ownership for newly-created Activities.
        if self.created_by_id:
            return self.created_by.full_name or self.created_by.username
        return ""

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.title)[:210] or "activite"
            candidate, suffix = base, 2
            qs = self._slug_scope()
            while qs.filter(slug=candidate).exists():
                candidate = f"{base[:225]}-{suffix}"
                suffix += 1
            self.slug = candidate
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.title


class OccurrenceStatus(models.TextChoices):
    DRAFT = "draft", "Brouillon"
    SCHEDULED = "scheduled", "Planifiée"
    CANCELLED = "cancelled", "Annulée"
    COMPLETED = "completed", "Terminée"


class Occurrence(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    activity = models.ForeignKey(Activity, on_delete=models.CASCADE, related_name="occurrences")
    label = models.CharField(max_length=180, blank=True)
    start_at = models.DateTimeField()
    end_at = models.DateTimeField(null=True, blank=True)
    timezone = models.CharField(max_length=100, default="Africa/Lubumbashi", validators=[validate_timezone_name])
    status = models.CharField(max_length=20, choices=OccurrenceStatus.choices, default=OccurrenceStatus.DRAFT)
    places = models.ManyToManyField("geography.Place", through="OccurrencePlace", related_name="occurrences", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["start_at", "id"]
        constraints = [
            models.CheckConstraint(condition=Q(end_at__isnull=True) | Q(end_at__gt=models.F("start_at")), name="activities_occ_end_after_start"),
            models.CheckConstraint(condition=~Q(timezone=""), name="activities_occ_timezone_present"),
        ]
        indexes = [
            models.Index(fields=["activity", "start_at"], name="activities_occ_activity_idx"),
            models.Index(fields=["status", "start_at"], name="activities_occ_status_idx"),
        ]

    def clean(self):
        super().clean()
        self.timezone = (self.timezone or "").strip()
        if self.start_at and self.end_at and self.end_at <= self.start_at:
            raise ValidationError({"end_at": "La fin doit être postérieure au début."})

    @property
    def is_future(self):
        return self.start_at > timezone.now()

    @property
    def is_ongoing(self):
        now = timezone.now()
        return self.start_at <= now and (self.end_at is None or self.end_at > now)

    def save(self, *args, **kwargs):
        self.timezone = (self.timezone or "").strip()
        self.full_clean()
        return super().save(*args, **kwargs)


class OccurrencePlaceRole(models.TextChoices):
    PRIMARY = "primary", "Lieu principal"
    MEETING_POINT = "meeting_point", "Point de rendez-vous"
    SERVICE_POINT = "service_point", "Point de service"
    OTHER = "other", "Autre"


class OccurrencePlace(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    occurrence = models.ForeignKey(Occurrence, on_delete=models.CASCADE, related_name="place_links")
    place = models.ForeignKey("geography.Place", on_delete=models.PROTECT, related_name="occurrence_links")
    role = models.CharField(max_length=24, choices=OccurrencePlaceRole.choices, default=OccurrencePlaceRole.OTHER)
    position = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["position", "role", "place__name"]
        constraints = [
            models.UniqueConstraint(fields=["occurrence", "place", "role"], name="activities_occ_place_unique"),
            models.UniqueConstraint(fields=["occurrence"], condition=Q(role=OccurrencePlaceRole.PRIMARY), name="activities_occ_primary_unique"),
        ]
        indexes = [
            models.Index(fields=["occurrence"], name="activities_occ_place_occ_idx"),
            models.Index(fields=["place"], name="activities_occ_place_geo_idx"),
        ]
