import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

from events.models import Event
from tickets.models import Ticket


class ScanResult(models.TextChoices):
    ACCEPTED = "accepted", "Accès autorisé"
    DUPLICATE = "duplicate", "Billet déjà utilisé"
    INVALID_TOKEN = "invalid_token", "QR invalide"
    UNKNOWN_TICKET = "unknown_ticket", "Billet introuvable"
    WRONG_EVENT = "wrong_event", "Mauvais événement"
    INVALID_STATUS = "invalid_status", "Billet non valide"
    EVENT_UNAVAILABLE = "event_unavailable", "Événement indisponible"


class ScannerAssignment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(
        Event,
        on_delete=models.PROTECT,
        related_name="scanner_assignments",
    )
    agent = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="scanner_assignments",
    )
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="scanner_assignments_created",
        null=True,
        blank=True,
    )
    label = models.CharField(max_length=120, default="Entrée principale")
    is_active = models.BooleanField(default=True)
    valid_from = models.DateTimeField(null=True, blank=True)
    valid_until = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["event__start_at", "label", "agent__username"]
        verbose_name = "affectation scanner"
        verbose_name_plural = "affectations scanner"
        constraints = [
            models.UniqueConstraint(
                fields=["event", "agent"],
                name="scanner_unique_event_agent",
            ),
            models.CheckConstraint(
                condition=(
                    Q(valid_from__isnull=True)
                    | Q(valid_until__isnull=True)
                    | Q(valid_until__gt=F("valid_from"))
                ),
                name="scanner_assignment_valid_window",
            ),
        ]
        indexes = [
            models.Index(
                fields=["event", "is_active"],
                name="scanner_assign_event_idx",
            ),
            models.Index(
                fields=["agent", "is_active"],
                name="scanner_assign_agent_idx",
            ),
        ]

    def clean(self):
        super().clean()
        if self.valid_from and self.valid_until and self.valid_until <= self.valid_from:
            raise ValidationError(
                {"valid_until": "La fin d’affectation doit être postérieure au début."}
            )

    @property
    def is_current(self):
        if not self.is_active:
            return False
        now = timezone.now()
        if self.valid_from and now < self.valid_from:
            return False
        if self.valid_until and now > self.valid_until:
            return False
        return True

    def __str__(self):
        return f"{self.event.title} — {self.agent.username} ({self.label})"


class ScanLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(
        Event,
        on_delete=models.PROTECT,
        related_name="scan_logs",
    )
    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.PROTECT,
        related_name="scan_logs",
        null=True,
        blank=True,
    )
    scanner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="scan_logs",
    )
    assignment = models.ForeignKey(
        ScannerAssignment,
        on_delete=models.SET_NULL,
        related_name="scan_logs",
        null=True,
        blank=True,
    )
    result = models.CharField(max_length=32, choices=ScanResult.choices)
    message = models.CharField(max_length=255)
    qr_fingerprint = models.CharField(
        max_length=64,
        blank=True,
        help_text="SHA-256 du jeton présenté. Le QR brut n’est jamais journalisé.",
    )
    client_reference = models.CharField(
        max_length=64,
        blank=True,
        help_text="Identifiant idempotent généré par le terminal de scan.",
    )
    gate = models.CharField(max_length=120, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    scanned_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        ordering = ["-scanned_at"]
        verbose_name = "journal de scan"
        verbose_name_plural = "journaux de scan"
        constraints = [
            models.UniqueConstraint(
                fields=["ticket"],
                condition=Q(result=ScanResult.ACCEPTED),
                name="scanner_one_accept_per_ticket",
            ),
            models.UniqueConstraint(
                fields=["scanner", "client_reference"],
                condition=~Q(client_reference=""),
                name="scanner_unique_client_ref",
            ),
        ]
        indexes = [
            models.Index(
                fields=["event", "scanned_at"],
                name="scanner_event_time_idx",
            ),
            models.Index(
                fields=["scanner", "scanned_at"],
                name="scanner_agent_time_idx",
            ),
            models.Index(
                fields=["ticket", "scanned_at"],
                name="scanner_ticket_time_idx",
            ),
            models.Index(
                fields=["result", "scanned_at"],
                name="scanner_result_time_idx",
            ),
        ]

    @property
    def accepted(self):
        return self.result == ScanResult.ACCEPTED

    def __str__(self):
        ticket = str(self.ticket.code) if self.ticket_id else "sans billet"
        return f"{self.get_result_display()} — {ticket}"
