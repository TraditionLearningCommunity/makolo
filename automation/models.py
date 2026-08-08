import uuid

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from events.models import Event


class AutomationRunStatus(models.TextChoices):
    SUCCESS = "success", "Réussi"
    FAILED = "failed", "Échoué"
    SKIPPED = "skipped", "Ignoré"


class EventAutomationPolicy(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.OneToOneField(
        Event,
        on_delete=models.CASCADE,
        related_name="automation_policy",
    )
    is_active = models.BooleanField(default=True)

    reminder_7d_enabled = models.BooleanField(default=False)
    reminder_24h_enabled = models.BooleanField(default=True)
    reminder_2h_enabled = models.BooleanField(default=True)
    post_event_followup_enabled = models.BooleanField(default=True)

    auto_complete_event = models.BooleanField(default=True)
    auto_close_sales_at_start = models.BooleanField(default=True)

    capacity_alerts_enabled = models.BooleanField(default=True)
    capacity_alert_percent = models.PositiveSmallIntegerField(
        default=80,
        validators=[MinValueValidator(1), MaxValueValidator(100)],
    )
    low_stock_alerts_enabled = models.BooleanField(default=True)
    low_stock_threshold = models.PositiveIntegerField(default=10)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["event__start_at"]

    def __str__(self):
        return f"Autopilot — {self.event.title}"


class AutomationRun(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name="automation_runs",
        null=True,
        blank=True,
    )
    rule_key = models.CharField(max_length=80)
    dedup_key = models.CharField(max_length=255, unique=True)
    status = models.CharField(
        max_length=16,
        choices=AutomationRunStatus.choices,
        default=AutomationRunStatus.SUCCESS,
    )
    summary = models.CharField(max_length=255, blank=True)
    payload = models.JSONField(default=dict, blank=True)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["rule_key", "created_at"]),
            models.Index(fields=["event", "created_at"]),
        ]

    def __str__(self):
        return f"{self.rule_key} — {self.status}"
