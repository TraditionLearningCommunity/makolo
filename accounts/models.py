import re
import uuid

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.contrib.contenttypes.fields import GenericRelation
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from geography.validators import validate_timezone_name


# =========================================================
# HELPERS
# =========================================================

def user_avatar_path(instance, filename):
    return f"accounts/users/{instance.id}/avatar/{filename}"


def verification_document_path(instance, filename):
    return f"accounts/users/{instance.user.id}/verification/{filename}"


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
    # Makolo currently ships with French as its configured Django locale. Add
    # another value only when that locale is genuinely supported by the app.
    FRENCH = "fr", "Français"


# =========================================================
# ABSTRACTS
# =========================================================

class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class UUIDModel(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    class Meta:
        abstract = True


# =========================================================
# ROLE
# =========================================================

class Role(UUIDModel, TimeStampedModel):
    """
    Roles dynamiques pour éviter
    les limitations des simples choices.
    """

    name = models.CharField(
        max_length=100,
        unique=True
    )

    code = models.SlugField(
        unique=True
    )

    description = models.TextField(
        blank=True,
        null=True
    )

    priority = models.PositiveIntegerField(
        default=0
    )

    is_system = models.BooleanField(
        default=False
    )

    is_active = models.BooleanField(
        default=True
    )

    class Meta:
        ordering = ["priority", "name"]

    def __str__(self):
        return self.name


# =========================================================
# PERMISSION GROUP
# =========================================================

class PermissionGroup(UUIDModel, TimeStampedModel):
    """
    Préparation pour RBAC évolutif.
    """

    name = models.CharField(
        max_length=120,
        unique=True
    )

    code = models.SlugField(
        unique=True
    )

    description = models.TextField(
        blank=True,
        null=True
    )

    roles = models.ManyToManyField(
        Role,
        blank=True,
        related_name="permission_groups"
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


# =========================================================
# USER
# =========================================================

class User(AbstractUser, UUIDModel, TimeStampedModel):

    # =====================================================
    # IDENTITÉ
    # =====================================================

    email = models.EmailField(
        unique=True
    )

    username = models.CharField(
        max_length=150,
        unique=True
    )

    phone = models.CharField(
        max_length=30,
        validators=[validate_phone_number],
        blank=True,
        null=True
    )

    birth_date = models.DateField(
        blank=True,
        null=True
    )

    gender = models.CharField(
        max_length=20,
        choices=GenderCode.choices,
        default=GenderCode.UNSPECIFIED,
        blank=True,
        null=True
    )

    bio = models.TextField(
        blank=True,
        null=True
    )

    avatar = models.ImageField(
        upload_to=user_avatar_path,
        blank=True,
        null=True
    )

    language = models.CharField(
        max_length=20,
        choices=LanguageCode.choices,
        default=LanguageCode.FRENCH
    )

    timezone = models.CharField(
        max_length=100,
        default="Africa/Lubumbashi",
        validators=[validate_timezone_name]
    )

    # =====================================================
    # ACCOUNT STATUS
    # =====================================================

    is_verified = models.BooleanField(
        default=False
    )

    email_verified = models.BooleanField(
        default=False
    )

    phone_verified = models.BooleanField(
        default=False
    )

    # Historical compatibility markers. Contextual authority must use Mandates.
    is_organizer = models.BooleanField(
        default=False
    )

    is_scanner_agent = models.BooleanField(
        default=False
    )

    onboarding_completed = models.BooleanField(
        default=False
    )

    onboarding_step = models.PositiveIntegerField(
        default=0
    )

    # =====================================================
    # SECURITY
    # =====================================================

    last_seen = models.DateTimeField(
        blank=True,
        null=True
    )

    last_login_ip = models.GenericIPAddressField(
        blank=True,
        null=True
    )

    failed_login_attempts = models.PositiveIntegerField(
        default=0
    )

    account_locked_until = models.DateTimeField(
        blank=True,
        null=True
    )

    require_2fa = models.BooleanField(
        default=False
    )

    # =====================================================
    # BUSINESS / RELATIONS
    # =====================================================

    roles = models.ManyToManyField(
        Role,
        blank=True,
        related_name="users"
    )

    permission_groups = models.ManyToManyField(
        PermissionGroup,
        blank=True,
        related_name="users"
    )

    # =====================================================
    # SOCIAL / NETWORK
    # =====================================================

    website = models.URLField(
        blank=True,
        null=True
    )

    linkedin_url = models.URLField(
        blank=True,
        null=True
    )

    facebook_url = models.URLField(
        blank=True,
        null=True
    )

    instagram_url = models.URLField(
        blank=True,
        null=True
    )

    x_url = models.URLField(
        blank=True,
        null=True
    )

    # =====================================================
    # METADATA
    # =====================================================

    metadata = models.JSONField(
        default=dict,
        blank=True
    )

    preferences = models.JSONField(
        default=dict,
        blank=True
    )

    settings_data = models.JSONField(
        default=dict,
        blank=True
    )

    analytics_data = models.JSONField(
        default=dict,
        blank=True
    )

    # =====================================================
    # AUTH CONFIG
    # =====================================================

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["email"]),
            models.Index(fields=["username"]),
            models.Index(fields=["phone"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["is_verified"]),
        ]

    def __str__(self):
        return self.email

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()


# =========================================================
# USER PROFILE
# =========================================================

class UserProfile(UUIDModel, TimeStampedModel):

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile"
    )

    company_name = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    organization_name = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    profession = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    country = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )

    city = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )

    address = models.TextField(
        blank=True,
        null=True
    )

    latitude = models.FloatField(
        blank=True,
        null=True
    )

    longitude = models.FloatField(
        blank=True,
        null=True
    )

    theme = models.CharField(
        max_length=50,
        default="system"
    )

    profile_completed = models.BooleanField(
        default=False
    )

    public_profile = models.BooleanField(
        default=False
    )

    searchable = models.BooleanField(
        default=True
    )

    def __str__(self):
        return f"{self.user.email} Profile"


# =========================================================
# USER DEVICE
# =========================================================

class UserDevice(UUIDModel, TimeStampedModel):

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="devices"
    )

    # SHA-256 of an opaque, non-authenticating HttpOnly browser identifier.
    # The raw value is never stored server-side and is not a session grant.
    device_key_hash = models.CharField(
        max_length=64,
        blank=True,
        default="",
        db_index=True
    )

    device_name = models.CharField(
        max_length=255
    )

    device_type = models.CharField(
        max_length=100
    )

    browser = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )

    os = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )

    ip_address = models.GenericIPAddressField(
        blank=True,
        null=True
    )

    trusted = models.BooleanField(
        default=False
    )

    last_used = models.DateTimeField(
        blank=True,
        null=True
    )

    metadata = models.JSONField(
        default=dict,
        blank=True
    )

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


# =========================================================
# SESSION LOG
# =========================================================

class UserSession(UUIDModel, TimeStampedModel):

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sessions"
    )

    session_key = models.CharField(
        max_length=255
    )

    ip_address = models.GenericIPAddressField()

    user_agent = models.TextField()

    started_at = models.DateTimeField(
        auto_now_add=True
    )

    ended_at = models.DateTimeField(
        blank=True,
        null=True
    )

    active = models.BooleanField(
        default=True
    )

    metadata = models.JSONField(
        default=dict,
        blank=True
    )

    def __str__(self):
        return f"{self.user.email} session"


# =========================================================
# VERIFICATION DOCUMENT
# =========================================================

class VerificationDocument(UUIDModel, TimeStampedModel):

    DOCUMENT_TYPES = (
        ("id_card", "ID Card"),
        ("passport", "Passport"),
        ("business_license", "Business License"),
        ("other", "Other"),
    )

    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="verification_documents"
    )

    document_type = models.CharField(
        max_length=100,
        choices=DOCUMENT_TYPES
    )

    file = models.FileField(
        upload_to=verification_document_path
    )

    status = models.CharField(
        max_length=50,
        choices=STATUS_CHOICES,
        default="pending"
    )

    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="reviewed_documents"
    )

    reviewed_at = models.DateTimeField(
        blank=True,
        null=True
    )

    notes = models.TextField(
        blank=True,
        null=True
    )

    metadata = models.JSONField(
        default=dict,
        blank=True
    )

    def __str__(self):
        return f"{self.user.email} - {self.document_type}"


# =========================================================
# USER ACTIVITY
# =========================================================

class UserActivity(UUIDModel, TimeStampedModel):

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="activities"
    )

    action = models.CharField(
        max_length=255
    )

    category = models.CharField(
        max_length=100
    )

    ip_address = models.GenericIPAddressField(
        blank=True,
        null=True
    )

    user_agent = models.TextField(
        blank=True,
        null=True
    )

    metadata = models.JSONField(
        default=dict,
        blank=True
    )

    def __str__(self):
        return f"{self.user.email} - {self.action}"


# =========================================================
# NOTIFICATION PREFERENCE
# =========================================================

class NotificationPreference(UUIDModel, TimeStampedModel):

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notification_preferences"
    )

    email_notifications = models.BooleanField(
        default=True
    )

    sms_notifications = models.BooleanField(
        default=True
    )

    push_notifications = models.BooleanField(
        default=True
    )

    marketing_notifications = models.BooleanField(
        default=False
    )

    security_notifications = models.BooleanField(
        default=True
    )

    event_notifications = models.BooleanField(
        default=True
    )

    quiet_hours_enabled = models.BooleanField(
        default=False
    )

    quiet_hours_start = models.TimeField(
        blank=True,
        null=True
    )

    quiet_hours_end = models.TimeField(
        blank=True,
        null=True
    )

    def __str__(self):
        return f"{self.user.email} notification preferences"
