import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.text import slugify

from .validators import validate_event_cover


class EventStatus(models.TextChoices):
    DRAFT = "draft", "Brouillon"
    PUBLISHED = "published", "Publié"
    CANCELLED = "cancelled", "Annulé"
    COMPLETED = "completed", "Terminé"


class EventVisibility(models.TextChoices):
    PUBLIC = "public", "Public"
    UNLISTED = "unlisted", "Non répertorié"
    PRIVATE = "private", "Privé"


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
            candidate = base
            suffix = 2
            while EventCategory.objects.exclude(pk=self.pk).filter(
                slug=candidate
            ).exists():
                candidate = f"{base[:110]}-{suffix}"
                suffix += 1
            self.slug = candidate
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class EventVenue(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=180)
    kind = models.CharField(
        max_length=20,
        choices=VenueKind.choices,
        default=VenueKind.PHYSICAL,
    )
    address = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=120, blank=True)
    country = models.CharField(max_length=120, blank=True)
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
    )
    online_url = models.URLField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name", "city"]
        verbose_name = "lieu d’événement"
        verbose_name_plural = "lieux d’événements"

    def clean(self):
        super().clean()
        errors = {}
        if self.kind in {VenueKind.ONLINE, VenueKind.HYBRID} and not self.online_url:
            errors["online_url"] = (
                "Une URL est requise pour un événement en ligne ou hybride."
            )
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        if self.city:
            return f"{self.name} — {self.city}"
        return self.name


class Event(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organizer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="organized_events",
    )
    category = models.ForeignKey(
        EventCategory,
        on_delete=models.SET_NULL,
        related_name="events",
        null=True,
        blank=True,
    )
    venue = models.ForeignKey(
        EventVenue,
        on_delete=models.SET_NULL,
        related_name="events",
        null=True,
        blank=True,
    )

    title = models.CharField(max_length=220)
    slug = models.SlugField(max_length=240, unique=True, blank=True)
    short_description = models.CharField(max_length=320, blank=True)
    description = models.TextField(blank=True)
    cover_image = models.ImageField(
        upload_to=event_cover_path,
        validators=[validate_event_cover],
        blank=True,
        null=True,
    )

    status = models.CharField(
        max_length=20,
        choices=EventStatus.choices,
        default=EventStatus.DRAFT,
    )
    visibility = models.CharField(
        max_length=20,
        choices=EventVisibility.choices,
        default=EventVisibility.PUBLIC,
    )

    start_at = models.DateTimeField()
    end_at = models.DateTimeField()
    registration_start_at = models.DateTimeField(null=True, blank=True)
    registration_end_at = models.DateTimeField(null=True, blank=True)
    timezone = models.CharField(max_length=100, default="Africa/Lubumbashi")
    capacity = models.PositiveIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
        help_text="Laisser vide pour une capacité illimitée.",
    )

    published_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["start_at", "title"]
        verbose_name = "événement"
        verbose_name_plural = "événements"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(end_at__gt=models.F("start_at")),
                name="event_end_after_start",
            ),
        ]

    def clean(self):
        super().clean()
        errors = {}

        if self.start_at and self.end_at and self.end_at <= self.start_at:
            errors["end_at"] = "La fin doit être postérieure au début."

        if (
            self.registration_start_at
            and self.registration_end_at
            and self.registration_end_at <= self.registration_start_at
        ):
            errors["registration_end_at"] = (
                "La fin des inscriptions doit être postérieure à leur début."
            )

        if self.registration_end_at and self.end_at:
            if self.registration_end_at > self.end_at:
                errors["registration_end_at"] = (
                    "Les inscriptions ne peuvent pas se terminer après l’événement."
                )

        if self.registration_start_at and self.end_at:
            if self.registration_start_at >= self.end_at:
                errors["registration_start_at"] = (
                    "Les inscriptions doivent commencer avant la fin de l’événement."
                )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.title)[:200] or "evenement"
            candidate = base
            suffix = 2
            while Event.objects.exclude(pk=self.pk).filter(slug=candidate).exists():
                candidate = f"{base[:225]}-{suffix}"
                suffix += 1
            self.slug = candidate
        super().save(*args, **kwargs)

    @property
    def is_upcoming(self):
        return self.start_at > timezone.now()

    @property
    def is_registration_open(self):
        now = timezone.now()
        if self.status != EventStatus.PUBLISHED:
            return False
        if self.registration_start_at and now < self.registration_start_at:
            return False
        if self.registration_end_at and now > self.registration_end_at:
            return False
        return now < self.end_at

    def __str__(self):
        return self.title
