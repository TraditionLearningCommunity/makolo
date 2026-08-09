import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import F, Q
from django.utils import timezone
from django.utils.text import slugify

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
    GATE_UNAVAILABLE = "gate_unavailable", "Porte indisponible"


class EventAccessGate(models.Model):
    """Porte/zone d'accès configurée pour un événement.

    Le journal conserve aussi le libellé texte `ScanLog.gate` comme snapshot
    historique. La relation `access_gate` permet ensuite les agrégations live
    sans casser les scans hérités ou les terminaux qui n'envoient qu'un nom.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name="access_gates",
    )
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, blank=True)
    description = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    throughput_target_per_minute = models.PositiveSmallIntegerField(
        default=20,
        validators=[MinValueValidator(1), MaxValueValidator(600)],
        help_text="Débit cible accepté par minute pour détecter la congestion.",
    )
    warning_rejection_rate = models.PositiveSmallIntegerField(
        default=30,
        validators=[MinValueValidator(1), MaxValueValidator(100)],
        help_text="Taux de refus à partir duquel la porte est signalée.",
    )
    priority = models.PositiveSmallIntegerField(default=100)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="access_gates_created",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["event__start_at", "priority", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["event", "slug"],
                name="scanner_gate_event_slug_unique",
            ),
            models.CheckConstraint(
                condition=Q(throughput_target_per_minute__gt=0),
                name="scanner_gate_throughput_positive",
            ),
        ]
        indexes = [
            models.Index(fields=["event", "is_active"], name="scanner_gate_event_active_idx"),
            models.Index(fields=["event", "priority"], name="scanner_gate_event_priority_idx"),
        ]

    def clean(self):
        super().clean()
        self.name = (self.name or "").strip()
        if not self.name:
            raise ValidationError({"name": "Le nom de la porte est obligatoire."})

    def save(self, *args, **kwargs):
        self.name = (self.name or "").strip()
        if not self.slug:
            base = slugify(self.name)[:110] or "porte"
            candidate = base
            suffix = 2
            while EventAccessGate.objects.exclude(pk=self.pk).filter(
                event_id=self.event_id,
                slug=candidate,
            ).exists():
                candidate = f"{base[:125]}-{suffix}"
                suffix += 1
            self.slug = candidate
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.event.title} — {self.name}"


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
    access_gate = models.ForeignKey(
        EventAccessGate,
        on_delete=models.SET_NULL,
        related_name="assignments",
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
        errors = {}
        if self.valid_from and self.valid_until and self.valid_until <= self.valid_from:
            errors["valid_until"] = "La fin d’affectation doit être postérieure au début."
        if self.access_gate_id and self.event_id and self.access_gate.event_id != self.event_id:
            errors["access_gate"] = "Cette porte appartient à un autre événement."
        if errors:
            raise ValidationError(errors)

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
    access_gate = models.ForeignKey(
        EventAccessGate,
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
            models.Index(
                fields=["access_gate", "scanned_at"],
                name="scanner_gate_time_idx",
            ),
        ]

    @property
    def accepted(self):
        return self.result == ScanResult.ACCEPTED

    def __str__(self):
        ticket = str(self.ticket.code) if self.ticket_id else "sans billet"
        return f"{self.get_result_display()} — {ticket}"
