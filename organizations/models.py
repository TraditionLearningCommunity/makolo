import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.text import slugify


class OrganizationVerificationStatus(models.TextChoices):
    NEW = "new", "Nouveau"
    PENDING = "pending", "Vérification en cours"
    VERIFIED = "verified", "Vérifié"
    SUSPENDED = "suspended", "Suspendu"


class OrganizationRole(models.TextChoices):
    OWNER = "owner", "Propriétaire"
    ADMIN = "admin", "Administrateur"
    EVENT_MANAGER = "event_manager", "Gestionnaire d'événements"
    FINANCE = "finance", "Finance"
    MARKETING = "marketing", "Marketing / Communication"
    SCANNER_MANAGER = "scanner_manager", "Responsable accès"


class Organization(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=180)
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    description = models.TextField(blank=True)
    website = models.URLField(blank=True)
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=40, blank=True)
    country = models.CharField(max_length=120, blank=True)
    city = models.CharField(max_length=120, blank=True)
    public_profile = models.BooleanField(default=True)
    verification_status = models.CharField(
        max_length=20,
        choices=OrganizationVerificationStatus.choices,
        default=OrganizationVerificationStatus.NEW,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_organizations",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["verification_status", "public_profile"]),
            models.Index(fields=["created_at"]),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name)[:170] or "organisation"
            candidate = base
            suffix = 2
            while Organization.objects.exclude(pk=self.pk).filter(slug=candidate).exists():
                candidate = f"{base[:185]}-{suffix}"
                suffix += 1
            self.slug = candidate
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class OrganizationMembership(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="organization_memberships",
    )
    role = models.CharField(
        max_length=24,
        choices=OrganizationRole.choices,
        default=OrganizationRole.EVENT_MANAGER,
    )
    is_active = models.BooleanField(default=True)
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="organization_invitations_sent",
        null=True,
        blank=True,
    )
    joined_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["organization__name", "user__email"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "user"],
                name="organization_membership_unique_user",
            )
        ]
        indexes = [
            models.Index(fields=["user", "is_active"]),
            models.Index(fields=["organization", "role", "is_active"]),
        ]

    def clean(self):
        super().clean()
        if self.pk:
            old = OrganizationMembership.objects.filter(pk=self.pk).first()
            if (
                old
                and old.role == OrganizationRole.OWNER
                and self.role != OrganizationRole.OWNER
                and not OrganizationMembership.objects.filter(
                    organization=self.organization,
                    role=OrganizationRole.OWNER,
                    is_active=True,
                ).exclude(pk=self.pk).exists()
            ):
                raise ValidationError("Une organisation doit conserver au moins un propriétaire actif.")

    def __str__(self):
        return f"{self.user} — {self.organization} ({self.get_role_display()})"
