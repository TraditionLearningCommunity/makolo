import re
import uuid

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from geography.validators import validate_timezone_name


def user_avatar_path(instance, filename):
    return f"accounts/users/{instance.id}/avatar/{filename}"


def verification_document_path(instance, filename):
    """Historical migration callable only.

    ``accounts.VerificationDocument`` has been removed from runtime ownership in
    favour of Trust, but old migrations must remain importable on a fresh DB.
    """
    user_id = getattr(instance, "user_id", None) or getattr(getattr(instance, "user", None), "id", "unknown")
    return f"accounts/users/{user_id}/verification/{filename}"


def validate_phone_number(value):
    """Accept common phone formatting while requiring a plausible digit count."""
    if value in (None, ""):
        return
    value = str(value).strip()
    if not re.fullmatch(r"\+?[0-9().\s-]+", value):
        raise ValidationError(
            "Saisissez un numéro de téléphone avec des chiffres et, si nécessaire, +, espaces, parenthèses, points ou tirets."
        )
    digit_count = len(re.sub(r"\D", "", value))
    if digit_count < 7 or digit_count > 15:
        raise ValidationError("Saisissez un numéro de téléphone contenant entre 7 et 15 chiffres.")


class GenderCode(models.TextChoices):
    MALE = "male", "Homme"
    FEMALE = "female", "Femme"
    UNSPECIFIED = "unspecified", "Non renseigné"


class LanguageCode(models.TextChoices):
    FRENCH = "fr", "Français"


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class UUIDModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class User(AbstractUser, UUIDModel, TimeStampedModel):
    """Technical account storage for the single global Makolo Profile identity.

    Business authority is never stored here. It belongs to authorization
    Role/Permission/Mandate. Trust verification is likewise owned by ``trust``.
    """

    email = models.EmailField(unique=True)
    username = models.CharField(max_length=150, unique=True)
    phone = models.CharField(
        max_length=30,
        validators=[validate_phone_number],
        blank=True,
        null=True,
    )
    birth_date = models.DateField(blank=True, null=True)
    gender = models.CharField(
        max_length=20,
        choices=GenderCode.choices,
        default=GenderCode.UNSPECIFIED,
        blank=True,
        null=True,
    )
    bio = models.TextField(blank=True, null=True)
    avatar = models.ImageField(upload_to=user_avatar_path, blank=True, null=True)
    language = models.CharField(
        max_length=20,
        choices=LanguageCode.choices,
        default=LanguageCode.FRENCH,
    )
    timezone = models.CharField(
        max_length=100,
        default="Africa/Lubumbashi",
        validators=[validate_timezone_name],
    )

    email_verified = models.BooleanField(default=False)
    phone_verified = models.BooleanField(default=False)
    onboarding_completed = models.BooleanField(default=False)
    onboarding_step = models.PositiveIntegerField(default=0)

    last_seen = models.DateTimeField(blank=True, null=True)
    last_login_ip = models.GenericIPAddressField(blank=True, null=True)
    failed_login_attempts = models.PositiveIntegerField(default=0)
    account_locked_until = models.DateTimeField(blank=True, null=True)
    require_2fa = models.BooleanField(default=False)

    website = models.URLField(blank=True, null=True)
    linkedin_url = models.URLField(blank=True, null=True)
    facebook_url = models.URLField(blank=True, null=True)
    instagram_url = models.URLField(blank=True, null=True)
    tiktok_url = models.URLField(blank=True, null=True)
    x_url = models.URLField(blank=True, null=True)
    youtube_url = models.URLField(blank=True, null=True)

    metadata = models.JSONField(default=dict, blank=True)
    preferences = models.JSONField(default=dict, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["email"]),
            models.Index(fields=["username"]),
            models.Index(fields=["phone"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return self.email

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()


class UserProfile(UUIDModel, TimeStampedModel):
    """One-to-one extension of the global Profile, never a second identity."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    company_name = models.CharField(max_length=255, blank=True, null=True)
    organization_name = models.CharField(max_length=255, blank=True, null=True)
    profession = models.CharField(max_length=255, blank=True, null=True)
    country = models.CharField(max_length=100, blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    latitude = models.FloatField(blank=True, null=True)
    longitude = models.FloatField(blank=True, null=True)
    theme = models.CharField(max_length=50, default="system")
    public_profile = models.BooleanField(default=False)
    searchable = models.BooleanField(default=False)

    def derive_profile_completed(self):
        """Compatibility helper for callers; completion itself is never persisted."""
        return bool(self.user.first_name and self.user.last_name and self.city)

    def __str__(self):
        return f"{self.user.email} Profile"


class UserDevice(UUIDModel, TimeStampedModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="devices",
    )
    device_key_hash = models.CharField(max_length=64, blank=True, default="", db_index=True)
    device_name = models.CharField(max_length=255)
    device_type = models.CharField(max_length=100)
    browser = models.CharField(max_length=100, blank=True, null=True)
    os = models.CharField(max_length=100, blank=True, null=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    trusted = models.BooleanField(default=False)
    last_used = models.DateTimeField(blank=True, null=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "device_key_hash"],
                condition=~Q(device_key_hash=""),
                name="accounts_device_user_key_unique",
            )
        ]

    def __str__(self):
        return f"{self.user.email} - {self.device_name}"


class UserSession(UUIDModel, TimeStampedModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sessions",
    )
    session_key = models.CharField(max_length=255)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(blank=True, null=True)
    active = models.BooleanField(default=True)
    metadata = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"{self.user.email} session"


class NotificationPreference(UUIDModel, TimeStampedModel):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notification_preferences",
    )
    email_notifications = models.BooleanField(default=True)
    sms_notifications = models.BooleanField(default=True)
    push_notifications = models.BooleanField(default=True)
    marketing_notifications = models.BooleanField(default=False)
    security_notifications = models.BooleanField(default=True)
    event_notifications = models.BooleanField(default=True)
    service_notifications = models.BooleanField(default=True)
    opportunity_notifications = models.BooleanField(default=True)
    quiet_hours_enabled = models.BooleanField(default=False)
    quiet_hours_start = models.TimeField(blank=True, null=True)
    quiet_hours_end = models.TimeField(blank=True, null=True)

    def __str__(self):
        return f"{self.user.email} notification preferences"
