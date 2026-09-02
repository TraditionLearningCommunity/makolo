from __future__ import annotations

import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from .capabilities import IntelligenceCapability


class ProviderProtocol(models.TextChoices):
    OPENAI_COMPATIBLE = "openai_compatible", "OpenAI-compatible"


class ProviderScope(models.TextChoices):
    PLATFORM = "platform", "Plateforme"
    SPACE = "space", "Espace"
    PROFILE = "profile", "Profil"


class ProviderHealth(models.TextChoices):
    UNKNOWN = "unknown", "Inconnu"
    HEALTHY = "healthy", "Disponible"
    DEGRADED = "degraded", "Dégradé"
    UNAVAILABLE = "unavailable", "Indisponible"
    INVALID_CREDENTIALS = "invalid_credentials", "Clé invalide"


class ProviderConnection(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120)
    protocol = models.CharField(max_length=32, choices=ProviderProtocol.choices)
    base_url = models.URLField(max_length=500)
    default_model = models.CharField(max_length=160)
    scope = models.CharField(max_length=16, choices=ProviderScope.choices, default=ProviderScope.PLATFORM)
    space = models.ForeignKey(
        "organizations.Organization",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="intelligence_provider_connections",
    )
    profile = models.ForeignKey(
        "accounts.UserProfile",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="intelligence_provider_connections",
    )
    enabled = models.BooleanField(default=False)
    priority = models.PositiveSmallIntegerField(default=100)
    timeout_seconds = models.PositiveSmallIntegerField(default=8)
    health_status = models.CharField(max_length=24, choices=ProviderHealth.choices, default=ProviderHealth.UNKNOWN)
    last_checked_at = models.DateTimeField(null=True, blank=True)
    last_latency_ms = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["priority", "name", "id"]
        indexes = [
            models.Index(fields=["enabled", "scope", "priority"], name="intel_conn_route_idx"),
            models.Index(fields=["health_status"], name="intel_conn_health_idx"),
        ]
        constraints = [
            models.CheckConstraint(condition=Q(timeout_seconds__gte=1), name="intel_conn_timeout_positive"),
            models.CheckConstraint(
                condition=(
                    Q(scope=ProviderScope.PLATFORM, space__isnull=True, profile__isnull=True)
                    | Q(scope=ProviderScope.SPACE, space__isnull=False, profile__isnull=True)
                    | Q(scope=ProviderScope.PROFILE, space__isnull=True, profile__isnull=False)
                ),
                name="intel_conn_scope_target_valid",
            ),
        ]

    def clean(self):
        super().clean()
        if self.scope == ProviderScope.PLATFORM and (self.space_id or self.profile_id):
            raise ValidationError("Une connexion plateforme ne cible ni Espace ni Profil.")
        if self.scope == ProviderScope.SPACE and (not self.space_id or self.profile_id):
            raise ValidationError("Une connexion Espace doit cibler exactement un Espace.")
        if self.scope == ProviderScope.PROFILE and (not self.profile_id or self.space_id):
            raise ValidationError("Une connexion Profil doit cibler exactement un Profil.")
        if self.timeout_seconds < 1:
            raise ValidationError({"timeout_seconds": "Le timeout doit être positif."})

    def __str__(self):
        return self.name


class ProviderCredential(models.Model):
    connection = models.OneToOneField(
        ProviderConnection,
        on_delete=models.CASCADE,
        related_name="credential",
        primary_key=True,
    )
    encrypted_secret = models.TextField()
    key_hint = models.CharField(max_length=32, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    rotated_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Credential({self.connection_id})"


class IntelligenceRoute(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    capability = models.CharField(
        max_length=32,
        choices=[(item.value, item.value) for item in IntelligenceCapability],
    )
    connection = models.ForeignKey(
        ProviderConnection,
        on_delete=models.CASCADE,
        related_name="routes",
    )
    model = models.CharField(max_length=160, blank=True)
    priority = models.PositiveSmallIntegerField(default=100)
    enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["priority", "id"]
        constraints = [
            models.UniqueConstraint(fields=["capability", "connection"], name="intel_route_capability_connection_unique"),
        ]
        indexes = [models.Index(fields=["capability", "enabled", "priority"], name="intel_route_lookup_idx")]

    def __str__(self):
        return f"{self.capability} -> {self.connection}"
