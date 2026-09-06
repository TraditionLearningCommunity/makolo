import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

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


class OccurrenceTimingKind(models.TextChoices):
    EXACT = "exact", "Date et heure exactes"
    DATE_ONLY = "date_only", "Date connue, heure à confirmer"
    ALL_DAY = "all_day", "Toute la journée"


class OccurrenceScheduleFrequency(models.TextChoices):
    DAILY = "daily", "Tous les jours"
    WEEKLY = "weekly", "Chaque semaine"
    MONTHLY = "monthly", "Chaque mois"
    YEARLY = "yearly", "Chaque année"


class OccurrenceScheduleStatus(models.TextChoices):
    ACTIVE = "active", "Actif"
    PAUSED = "paused", "En pause"
    RETIRED = "retired", "Retiré"


class OccurrenceSchedule(models.Model):
    """Calendar rule that materializes concrete Occurrences for one Activity."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    activity = models.ForeignKey(Activity, on_delete=models.CASCADE, related_name="occurrence_schedules")
    label = models.CharField(max_length=180, blank=True)
    timezone = models.CharField(max_length=100, default="Africa/Lubumbashi", validators=[validate_timezone_name])
    frequency = models.CharField(max_length=16, choices=OccurrenceScheduleFrequency.choices)
    interval = models.PositiveSmallIntegerField(default=1)
    starts_on = models.DateField()
    ends_on = models.DateField(null=True, blank=True)
    timing_kind = models.CharField(max_length=16, choices=OccurrenceTimingKind.choices, default=OccurrenceTimingKind.EXACT)
    start_time = models.TimeField(null=True, blank=True)
    duration_minutes = models.PositiveIntegerField(null=True, blank=True)
    month_day = models.PositiveSmallIntegerField(null=True, blank=True)
    month = models.PositiveSmallIntegerField(null=True, blank=True)
    occurrence_status = models.CharField(max_length=20, choices=OccurrenceStatus.choices, default=OccurrenceStatus.SCHEDULED)
    status = models.CharField(max_length=16, choices=OccurrenceScheduleStatus.choices, default=OccurrenceScheduleStatus.ACTIVE)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_occurrence_schedules",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["activity_id", "starts_on", "start_time", "id"]
        indexes = [
            models.Index(fields=["activity", "status"], name="activities_sched_activity_idx"),
            models.Index(fields=["status", "starts_on", "ends_on"], name="activities_sched_window_idx"),
        ]
        constraints = [
            models.CheckConstraint(condition=Q(interval__gt=0), name="activities_sched_interval_pos"),
            models.CheckConstraint(condition=Q(ends_on__isnull=True) | Q(ends_on__gte=models.F("starts_on")), name="activities_sched_window_valid"),
        ]

    def clean(self):
        super().clean()
        self.timezone = (self.timezone or "").strip()
        errors = {}
        if self.timing_kind == OccurrenceTimingKind.EXACT and self.start_time is None:
            errors["start_time"] = "Une récurrence à heure exacte exige une heure de début."
        if self.timing_kind != OccurrenceTimingKind.EXACT and self.start_time is not None:
            errors["start_time"] = "Une récurrence sans heure exacte ne doit pas stocker d'heure."
        if self.duration_minutes is not None and self.timing_kind != OccurrenceTimingKind.EXACT:
            errors["duration_minutes"] = "Une durée en minutes exige une heure exacte."
        if self.frequency == OccurrenceScheduleFrequency.MONTHLY and not self.month_day:
            errors["month_day"] = "Une récurrence mensuelle exige un jour du mois."
        if self.frequency == OccurrenceScheduleFrequency.YEARLY and (not self.month or not self.month_day):
            errors["month"] = "Une récurrence annuelle exige un mois et un jour."
        if self.month and not 1 <= self.month <= 12:
            errors["month"] = "Le mois doit être compris entre 1 et 12."
        if self.month_day and not 1 <= self.month_day <= 31:
            errors["month_day"] = "Le jour du mois doit être compris entre 1 et 31."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.timezone = (self.timezone or "").strip()
        self.full_clean()
        return super().save(*args, **kwargs)


class OccurrenceScheduleWeekday(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    schedule = models.ForeignKey(OccurrenceSchedule, on_delete=models.CASCADE, related_name="weekdays")
    weekday = models.PositiveSmallIntegerField(help_text="0=lundi … 6=dimanche")

    class Meta:
        ordering = ["weekday", "id"]
        constraints = [
            models.UniqueConstraint(fields=["schedule", "weekday"], name="activities_sched_weekday_unique"),
            models.CheckConstraint(condition=Q(weekday__gte=0, weekday__lte=6), name="activities_sched_weekday_valid"),
        ]

    def clean(self):
        super().clean()
        if self.weekday not in range(7):
            raise ValidationError({"weekday": "Le jour de semaine doit être compris entre 0 et 6."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class Occurrence(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    activity = models.ForeignKey(Activity, on_delete=models.CASCADE, related_name="occurrences")
    label = models.CharField(max_length=180, blank=True)
    start_date = models.DateField(null=True, blank=True)
    start_time = models.TimeField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    timing_kind = models.CharField(max_length=16, choices=OccurrenceTimingKind.choices, default=OccurrenceTimingKind.EXACT)
    # Compatibility projection for existing exact-time consumers. Date-only and
    # all-day Occurrences deliberately keep these NULL rather than invent 00:00.
    start_at = models.DateTimeField(null=True, blank=True)
    end_at = models.DateTimeField(null=True, blank=True)
    timezone = models.CharField(max_length=100, default="Africa/Lubumbashi", validators=[validate_timezone_name])
    status = models.CharField(max_length=20, choices=OccurrenceStatus.choices, default=OccurrenceStatus.DRAFT)
    schedule = models.ForeignKey(
        OccurrenceSchedule,
        on_delete=models.SET_NULL,
        related_name="generated_occurrences",
        null=True,
        blank=True,
    )
    schedule_local_date = models.DateField(null=True, blank=True)
    places = models.ManyToManyField("geography.Place", through="OccurrencePlace", related_name="occurrences", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["start_date", "start_time", "id"]
        constraints = [
            models.CheckConstraint(condition=~Q(timezone=""), name="activities_occ_timezone_present"),
            models.CheckConstraint(condition=Q(end_date__isnull=True) | Q(start_date__isnull=True) | Q(end_date__gte=models.F("start_date")), name="activities_occ_date_window"),
            models.UniqueConstraint(
                fields=["schedule", "schedule_local_date"],
                condition=Q(schedule__isnull=False),
                name="activities_occ_schedule_slot_unique",
            ),
        ]
        indexes = [
            models.Index(fields=["activity", "start_date", "start_time"], name="activities_occ_activity_idx"),
            models.Index(fields=["status", "start_date", "start_time"], name="activities_occ_status_idx"),
            models.Index(fields=["start_at"], name="activities_occ_startat_idx"),
        ]

    def _local_parts_from_instant(self, value):
        if value is None:
            return None, None
        local = value.astimezone(ZoneInfo(self.timezone))
        return local.date(), local.timetz().replace(tzinfo=None)

    def _instant_from_local(self, day, clock):
        if day is None or clock is None:
            return None
        return datetime.combine(day, clock, tzinfo=ZoneInfo(self.timezone))

    def clean(self):
        super().clean()
        self.timezone = (self.timezone or "").strip()
        errors = {}

        if self.start_at is not None and self.start_date is None:
            self.start_date, self.start_time = self._local_parts_from_instant(self.start_at)
            self.timing_kind = OccurrenceTimingKind.EXACT
        if self.end_at is not None and self.end_date is None:
            self.end_date, self.end_time = self._local_parts_from_instant(self.end_at)

        if self.start_date is None:
            errors["start_date"] = "La date de début est obligatoire."

        if self.timing_kind == OccurrenceTimingKind.EXACT:
            if self.start_time is None:
                errors["start_time"] = "Une Occurrence à heure exacte exige une heure de début."
            else:
                self.start_at = self._instant_from_local(self.start_date, self.start_time)
            if self.end_time is not None:
                effective_end_date = self.end_date or self.start_date
                self.end_date = effective_end_date
                self.end_at = self._instant_from_local(effective_end_date, self.end_time)
            elif self.end_date is not None and self.end_at is None:
                errors["end_time"] = "Une date de fin exacte exige une heure de fin."
        else:
            if self.start_time is not None or self.end_time is not None:
                errors["start_time"] = "Une Occurrence sans heure exacte ne doit pas stocker d'heure."
            self.start_at = None
            self.end_at = None
            if self.timing_kind == OccurrenceTimingKind.ALL_DAY and self.end_date is None:
                self.end_date = self.start_date

        if self.end_date and self.start_date and self.end_date < self.start_date:
            errors["end_date"] = "La fin doit être postérieure ou égale au début."
        if self.start_at and self.end_at and self.end_at <= self.start_at:
            errors["end_time"] = "La fin doit être postérieure au début."
        if self.schedule_id and self.schedule_local_date and self.start_date and self.schedule_local_date != self.start_date:
            errors["schedule_local_date"] = "Le slot généré doit correspondre à la date locale de l'Occurrence."
        if errors:
            raise ValidationError(errors)

    @property
    def is_future(self):
        if self.start_at is not None:
            return self.start_at > timezone.now()
        if self.start_date is None:
            return False
        today = timezone.now().astimezone(ZoneInfo(self.timezone)).date()
        return self.start_date > today

    @property
    def is_ongoing(self):
        now = timezone.now()
        if self.start_at is not None:
            return self.start_at <= now and (self.end_at is None or self.end_at > now)
        if self.start_date is None:
            return False
        local_today = now.astimezone(ZoneInfo(self.timezone)).date()
        if self.timing_kind == OccurrenceTimingKind.ALL_DAY:
            return self.start_date <= local_today <= (self.end_date or self.start_date)
        return False

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
