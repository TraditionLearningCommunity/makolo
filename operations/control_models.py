from django.conf import settings
from django.db import models


class OperationalControlCode(models.TextChoices):
    USER_SIGNUPS = "user_signups", "Nouveaux profils utilisateurs"
    ACCESS_ISSUANCE = "access_issuance", "Émission de nouveaux Access"
    PAYMENT_CREATION = "payment_creation", "Création de nouveaux paiements"
    AUTOPILOT = "autopilot", "Autopilot"


class OperationalControl(models.Model):
    """Small, explicit Operations-owned switches for reversible incident response."""

    code = models.CharField(
        max_length=40,
        choices=OperationalControlCode.choices,
        primary_key=True,
    )
    is_enabled = models.BooleanField(default=True)
    reason = models.TextField(blank=True)
    incident = models.ForeignKey(
        "operations.OperationsIncident",
        on_delete=models.SET_NULL,
        related_name="operational_controls",
        null=True,
        blank=True,
    )
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="operations_controls_changed",
        null=True,
        blank=True,
    )
    changed_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["code"]
        verbose_name = "contrôle opérationnel"
        verbose_name_plural = "contrôles opérationnels"

    def __str__(self):
        state = "actif" if self.is_enabled else "suspendu"
        return f"{self.get_code_display()} — {state}"
