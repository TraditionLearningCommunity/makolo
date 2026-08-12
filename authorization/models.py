import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q
from django.utils import timezone


class AuthorityScope(models.TextChoices):
    PLATFORM = "platform", "Plateforme Makolo"
    SPACE = "space", "Espace"


class MandateStatus(models.TextChoices):
    ACTIVE = "active", "Actif"
    SUSPENDED = "suspended", "Suspendu"
    REVOKED = "revoked", "Révoqué"


class Permission(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=120, unique=True)
    name = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    domain = models.CharField(max_length=80)
    scope_type = models.CharField(max_length=16, choices=AuthorityScope.choices)
    is_system = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["domain", "code"]
        indexes = [
            models.Index(fields=["scope_type", "is_active"], name="auth_perm_scope_active_idx"),
            models.Index(fields=["domain", "is_active"], name="auth_perm_domain_active_idx"),
        ]

    def __str__(self):
        return f"{self.code} — {self.name}"


class Role(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.SlugField(max_length=120)
    name = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    scope_type = models.CharField(max_length=16, choices=AuthorityScope.choices)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="custom_authorization_roles",
        null=True,
        blank=True,
        help_text="Renseigné uniquement pour un rôle personnalisé propre à un Espace.",
    )
    permissions = models.ManyToManyField(
        Permission,
        through="RolePermission",
        related_name="roles",
        blank=True,
    )
    is_system = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["scope_type", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["code"],
                condition=Q(is_system=True),
                name="auth_role_system_code_unique",
            ),
            models.UniqueConstraint(
                fields=["organization", "code"],
                condition=Q(is_system=False),
                name="auth_role_custom_space_code_unique",
            ),
            models.CheckConstraint(
                condition=(
                    Q(scope_type=AuthorityScope.PLATFORM, is_system=True, organization__isnull=True)
                    | Q(scope_type=AuthorityScope.SPACE, is_system=True, organization__isnull=True)
                    | Q(scope_type=AuthorityScope.SPACE, is_system=False, organization__isnull=False)
                ),
                name="auth_role_scope_organization_valid",
            ),
        ]
        indexes = [
            models.Index(fields=["scope_type", "is_active"], name="auth_role_scope_active_idx"),
            models.Index(fields=["organization", "is_active"], name="auth_role_org_active_idx"),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.scope_type == AuthorityScope.PLATFORM and (not self.is_system or self.organization_id):
            errors["scope_type"] = "Les rôles plateforme sont uniquement des rôles système Makolo."
        if self.scope_type == AuthorityScope.SPACE and not self.is_system and not self.organization_id:
            errors["organization"] = "Un rôle personnalisé Espace doit appartenir à un Espace."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return self.name


class RolePermission(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name="role_permissions")
    permission = models.ForeignKey(
        Permission,
        on_delete=models.PROTECT,
        related_name="role_permissions",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["role__name", "permission__code"]
        constraints = [
            models.UniqueConstraint(
                fields=["role", "permission"],
                name="auth_role_permission_unique",
            )
        ]
        indexes = [
            models.Index(fields=["permission", "role"], name="auth_role_perm_lookup_idx"),
        ]

    def clean(self):
        super().clean()
        if self.role_id and self.permission_id and self.role.scope_type != self.permission.scope_type:
            raise ValidationError("Le rôle et la permission doivent partager la même portée.")
        if (
            self.role_id
            and not self.role.is_system
            and self.permission_id
            and self.permission.scope_type != AuthorityScope.SPACE
        ):
            raise ValidationError("Un rôle personnalisé ne peut contenir que des permissions Espace.")

    def __str__(self):
        return f"{self.role} — {self.permission.code}"


class Mandate(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    profile = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="authority_mandates",
    )
    role = models.ForeignKey(Role, on_delete=models.PROTECT, related_name="mandates")
    scope_type = models.CharField(max_length=16, choices=AuthorityScope.choices)
    space = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="authority_mandates",
        null=True,
        blank=True,
    )
    status = models.CharField(
        max_length=16,
        choices=MandateStatus.choices,
        default=MandateStatus.ACTIVE,
    )
    valid_from = models.DateTimeField(null=True, blank=True)
    valid_until = models.DateTimeField(null=True, blank=True)
    granted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="authority_mandates_granted",
        null=True,
        blank=True,
    )
    granted_at = models.DateTimeField(default=timezone.now)
    revoked_at = models.DateTimeField(null=True, blank=True)
    source = models.CharField(max_length=80, default="service")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["scope_type", "space__name", "profile__email", "role__name"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(scope_type=AuthorityScope.PLATFORM, space__isnull=True)
                    | Q(scope_type=AuthorityScope.SPACE, space__isnull=False)
                ),
                name="auth_mandate_scope_space_valid",
            ),
            models.CheckConstraint(
                condition=(
                    Q(valid_until__isnull=True)
                    | Q(valid_from__isnull=True)
                    | Q(valid_until__gt=F("valid_from"))
                ),
                name="auth_mandate_valid_window",
            ),
            models.UniqueConstraint(
                fields=["profile", "role", "scope_type"],
                condition=Q(scope_type=AuthorityScope.PLATFORM, status=MandateStatus.ACTIVE),
                name="auth_mandate_active_platform_unique",
            ),
            models.UniqueConstraint(
                fields=["profile", "role", "scope_type", "space"],
                condition=Q(scope_type=AuthorityScope.SPACE, status=MandateStatus.ACTIVE),
                name="auth_mandate_active_space_unique",
            ),
        ]
        indexes = [
            models.Index(fields=["profile", "status"], name="auth_mand_prof_status_idx"),
            models.Index(fields=["scope_type", "status"], name="auth_mandate_scope_status_idx"),
            models.Index(fields=["space", "status"], name="auth_mandate_space_status_idx"),
            models.Index(fields=["valid_from", "valid_until"], name="auth_mandate_validity_idx"),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.scope_type == AuthorityScope.PLATFORM and self.space_id:
            errors["space"] = "Un Mandat plateforme ne cible aucun Espace."
        if self.scope_type == AuthorityScope.SPACE and not self.space_id:
            errors["space"] = "Un Mandat Espace doit cibler un Espace."
        if self.role_id and self.role.scope_type != self.scope_type:
            errors["role"] = "Le rôle ne correspond pas à la portée du Mandat."
        if self.valid_from and self.valid_until and self.valid_until <= self.valid_from:
            errors["valid_until"] = "La fin de validité doit être postérieure au début."
        if self.status == MandateStatus.REVOKED and not self.revoked_at:
            errors["revoked_at"] = "Un Mandat révoqué doit conserver sa date de révocation."
        if errors:
            raise ValidationError(errors)

    def is_current(self, at=None):
        at = at or timezone.now()
        if self.status != MandateStatus.ACTIVE or self.revoked_at:
            return False
        if not self.role.is_active:
            return False
        if self.valid_from and at < self.valid_from:
            return False
        if self.valid_until and at >= self.valid_until:
            return False
        return True

    def __str__(self):
        target = "Makolo" if self.scope_type == AuthorityScope.PLATFORM else self.space
        return f"{self.profile} — {self.role} — {target}"
