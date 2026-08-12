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
    """Legacy compatibility roles.

    Runtime authority is canonical in authorization.Mandate. Keep these values
    stable until all historical consumers and data have completed cutover.
    """

    OWNER = "owner", "Propriétaire"
    ADMIN = "admin", "Administrateur"
    EVENT_MANAGER = "event_manager", "Gestionnaire d'événements"
    FINANCE = "finance", "Finance"
    MARKETING = "marketing", "Marketing / Communication"
    SCANNER_MANAGER = "scanner_manager", "Responsable accès"


class TeamMembershipStatus(models.TextChoices):
    INVITED = "invited", "Invité"
    ACTIVE = "active", "Actif"
    INACTIVE = "inactive", "Inactif"


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
    verification_status = models.CharField(max_length=20, choices=OrganizationVerificationStatus.choices, default=OrganizationVerificationStatus.NEW)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_organizations")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["verification_status", "public_profile"], name="organizatio_verific_68b188_idx"),
            models.Index(fields=["created_at"], name="organizatio_created_dde2e1_idx"),
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


class Team(models.Model):
    """Operational collaboration group for one Makolo Espace.

    Membership is not authority. Permissions are resolved exclusively from
    authorization.Mandate.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="teams")
    name = models.CharField(max_length=160, default="Équipe principale")
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["organization__name", "name"]
        constraints = [
            models.UniqueConstraint(fields=["organization", "name"], name="team_org_name_unique"),
            models.UniqueConstraint(
                fields=["organization"],
                condition=models.Q(is_default=True),
                name="team_one_default_per_org",
            ),
        ]
        indexes = [
            models.Index(fields=["organization", "is_active"], name="team_org_active_idx"),
        ]

    def __str__(self):
        return f"{self.organization} — {self.name}"


class TeamMembership(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="team_memberships")
    status = models.CharField(
        max_length=16,
        choices=TeamMembershipStatus.choices,
        default=TeamMembershipStatus.ACTIVE,
    )
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="team_invitations_sent",
        null=True,
        blank=True,
    )
    joined_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["team__organization__name", "user__email"]
        constraints = [
            models.UniqueConstraint(fields=["team", "user"], name="team_membership_unique_user"),
        ]
        indexes = [
            models.Index(fields=["user", "status"], name="team_member_user_status_idx"),
            models.Index(fields=["team", "status"], name="team_member_team_status_idx"),
        ]

    @property
    def is_active(self):
        return self.status == TeamMembershipStatus.ACTIVE

    def __str__(self):
        return f"{self.user} — {self.team} ({self.get_status_display()})"


class OrganizationMembership(models.Model):
    """Legacy compatibility projection of one standard Espace responsibility.

    New authorization decisions must not read this model or ``role`` field.
    Services keep it synchronized while historical event/mobile paths migrate.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="organization_memberships")
    role = models.CharField(max_length=24, choices=OrganizationRole.choices, default=OrganizationRole.EVENT_MANAGER)
    is_active = models.BooleanField(default=True)
    invited_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="organization_invitations_sent", null=True, blank=True)
    joined_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["organization__name", "user__email"]
        constraints = [
            models.UniqueConstraint(fields=["organization", "user"], name="organization_membership_unique_user")
        ]
        indexes = [
            models.Index(fields=["user", "is_active"], name="organizatio_user_id_d45739_idx"),
            models.Index(fields=["organization", "role", "is_active"], name="organizatio_organiz_25f1f7_idx"),
        ]

    def clean(self):
        super().clean()
        if self.pk:
            old = OrganizationMembership.objects.filter(pk=self.pk).first()
            if old and old.role == OrganizationRole.OWNER and self.role != OrganizationRole.OWNER and not OrganizationMembership.objects.filter(
                organization=self.organization, role=OrganizationRole.OWNER, is_active=True
            ).exclude(pk=self.pk).exists():
                raise ValidationError("Une organisation doit conserver au moins un propriétaire actif.")

    def __str__(self):
        return f"{self.user} — {self.organization} ({self.get_role_display()})"


class OrganizationFollow(models.Model):
    """Relation sociale explicite entre un participant et un organisateur.

    Suivre un organisateur n'est pas un consentement marketing e-mail. Les
    préférences e-mail sont opt-in et restent subordonnées au réglage global du
    compte Makolo.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="followers",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="followed_organizations",
    )
    notify_new_events = models.BooleanField(default=True)
    notify_announcements = models.BooleanField(default=True)
    email_new_events = models.BooleanField(default=False)
    email_announcements = models.BooleanField(default=False)
    followed_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-followed_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "user"],
                name="organization_follow_unique_user",
            )
        ]
        indexes = [
            models.Index(fields=["organization", "followed_at"], name="org_follow_org_date_idx"),
            models.Index(fields=["user", "followed_at"], name="org_follow_user_date_idx"),
        ]

    def __str__(self):
        return f"{self.user} suit {self.organization}"
