import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from .validators import (
    normalize_country_code,
    validate_country_code,
    validate_timezone_name,
)
from .value_objects import GeoPoint


LATITUDE_MIN = Decimal("-90")
LATITUDE_MAX = Decimal("90")
LONGITUDE_MIN = Decimal("-180")
LONGITUDE_MAX = Decimal("180")


class Place(models.Model):
    """Reusable physical location. Ownership is expressed by domain relations."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=180)
    address_line = models.CharField(max_length=255, blank=True)
    locality = models.CharField(max_length=120, blank=True)
    administrative_area = models.CharField(max_length=120, blank=True)
    postal_code = models.CharField(max_length=32, blank=True)
    country_code = models.CharField(
        max_length=2,
        blank=True,
        validators=[validate_country_code],
    )
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
    timezone = models.CharField(
        max_length=100,
        blank=True,
        validators=[validate_timezone_name],
    )
    access_instructions = models.CharField(max_length=320, blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_places",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name", "locality"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(latitude__isnull=True, longitude__isnull=True)
                    | Q(latitude__isnull=False, longitude__isnull=False)
                ),
                name="geo_place_coordinates_pair",
            ),
            models.CheckConstraint(
                condition=(
                    Q(latitude__isnull=True)
                    | Q(latitude__gte=LATITUDE_MIN, latitude__lte=LATITUDE_MAX)
                ),
                name="geo_place_latitude_range",
            ),
            models.CheckConstraint(
                condition=(
                    Q(longitude__isnull=True)
                    | Q(longitude__gte=LONGITUDE_MIN, longitude__lte=LONGITUDE_MAX)
                ),
                name="geo_place_longitude_range",
            ),
        ]
        indexes = [
            models.Index(
                fields=["country_code", "locality", "is_active"],
                name="geo_place_country_local_idx",
            ),
            models.Index(fields=["latitude", "longitude"], name="geo_place_lat_lon_idx"),
        ]
        verbose_name = "lieu"
        verbose_name_plural = "lieux"

    def clean(self):
        super().clean()
        self.country_code = normalize_country_code(self.country_code)
        self.timezone = (self.timezone or "").strip()
        errors = {}
        has_latitude = self.latitude is not None
        has_longitude = self.longitude is not None
        if has_latitude != has_longitude:
            message = "Latitude et longitude doivent être renseignées ensemble ou laissées vides."
            errors["latitude"] = message
            errors["longitude"] = message
        if has_latitude and not LATITUDE_MIN <= self.latitude <= LATITUDE_MAX:
            errors["latitude"] = "La latitude doit être comprise entre -90 et 90."
        if has_longitude and not LONGITUDE_MIN <= self.longitude <= LONGITUDE_MAX:
            errors["longitude"] = "La longitude doit être comprise entre -180 et 180."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.country_code = normalize_country_code(self.country_code)
        self.full_clean()
        return super().save(*args, **kwargs)

    @property
    def point(self):
        if self.latitude is None or self.longitude is None:
            return None
        return GeoPoint(self.latitude, self.longitude)

    def __str__(self):
        return f"{self.name} — {self.locality}" if self.locality else self.name


class ZoneType(models.TextChoices):
    ADMINISTRATIVE = "administrative", "Administrative"
    RADIUS = "radius", "Rayon"


class Zone(models.Model):
    """Geographic perimeter. Polygonal geometry is deferred to PostGIS."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=180)
    zone_type = models.CharField(
        max_length=20,
        choices=ZoneType.choices,
        default=ZoneType.ADMINISTRATIVE,
    )
    country_code = models.CharField(
        max_length=2,
        blank=True,
        validators=[validate_country_code],
    )
    administrative_area = models.CharField(max_length=120, blank=True)
    locality = models.CharField(max_length=120, blank=True)
    center_place = models.ForeignKey(
        Place,
        on_delete=models.PROTECT,
        related_name="radius_zones",
        null=True,
        blank=True,
    )
    radius_m = models.PositiveIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_zones",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(
                        zone_type=ZoneType.ADMINISTRATIVE,
                        center_place__isnull=True,
                        radius_m__isnull=True,
                    )
                    | Q(
                        zone_type=ZoneType.RADIUS,
                        center_place__isnull=False,
                        radius_m__gt=0,
                    )
                ),
                name="geo_zone_shape_valid",
            )
        ]
        indexes = [
            models.Index(fields=["zone_type", "is_active"], name="geo_zone_type_active_idx"),
            models.Index(fields=["country_code", "is_active"], name="geo_zone_country_active_idx"),
        ]
        verbose_name = "zone"
        verbose_name_plural = "zones"

    def clean(self):
        super().clean()
        self.country_code = normalize_country_code(self.country_code)
        errors = {}
        if self.zone_type == ZoneType.RADIUS:
            if not self.center_place_id:
                errors["center_place"] = "Une zone par rayon doit avoir un lieu central."
            elif self.center_place.point is None:
                errors["center_place"] = "Le lieu central doit posséder des coordonnées valides."
            if not self.radius_m or self.radius_m <= 0:
                errors["radius_m"] = "Le rayon doit être strictement positif."
        else:
            if self.center_place_id:
                errors["center_place"] = "Une zone administrative n'utilise pas de lieu central."
            if self.radius_m is not None:
                errors["radius_m"] = "Une zone administrative n'utilise pas de rayon."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.country_code = normalize_country_code(self.country_code)
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class SpacePlaceRole(models.TextChoices):
    HEADQUARTERS = "headquarters", "Siège"
    OFFICE = "office", "Bureau"
    BRANCH = "branch", "Agence / succursale"
    SERVICE_POINT = "service_point", "Point de service"
    OTHER = "other", "Autre"


class SpacePlace(models.Model):
    """Explicit relationship between one Espace and one reusable Place."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="space_places",
    )
    place = models.ForeignKey(
        Place,
        on_delete=models.PROTECT,
        related_name="space_relations",
    )
    role = models.CharField(
        max_length=24,
        choices=SpacePlaceRole.choices,
        default=SpacePlaceRole.OTHER,
    )
    public_label = models.CharField(max_length=160, blank=True)
    is_primary = models.BooleanField(default=False)
    is_public = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    position = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["position", "role", "place__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "place", "role"],
                name="geo_space_place_role_unique",
            ),
            models.UniqueConstraint(
                fields=["organization", "role"],
                condition=Q(is_active=True, is_primary=True),
                name="geo_space_place_primary_role",
            ),
            models.CheckConstraint(
                condition=Q(is_primary=False) | Q(is_active=True),
                name="geo_space_primary_is_active",
            ),
        ]
        indexes = [
            models.Index(
                fields=["organization", "is_active"],
                name="geo_space_place_org_active_idx",
            ),
            models.Index(fields=["place", "is_active"], name="geo_space_place_active_idx"),
        ]
        verbose_name = "lieu d'Espace"
        verbose_name_plural = "lieux d'Espace"

    def clean(self):
        super().clean()
        if self.is_primary and not self.is_active:
            raise ValidationError({"is_primary": "Un lieu principal doit être actif."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.organization} — {self.place} ({self.get_role_display()})"
