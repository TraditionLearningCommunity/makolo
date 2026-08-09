import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class IncidentSeverity(models.TextChoices):
    LOW = "low", "Faible"
    MEDIUM = "medium", "Moyenne"
    HIGH = "high", "Élevée"
    CRITICAL = "critical", "Critique"


class IncidentStatus(models.TextChoices):
    OPEN = "open", "Ouvert"
    INVESTIGATING = "investigating", "En investigation"
    MONITORING = "monitoring", "Sous surveillance"
    RESOLVED = "resolved", "Résolu"
    DISMISSED = "dismissed", "Classé sans suite"


class IncidentCategory(models.TextChoices):
    ORGANIZATION = "organization", "Organisation"
    EVENT = "event", "Événement"
    PAYMENT = "payment", "Paiement"
    ACCESS = "access", "Accès / Scan"
    AUTOMATION = "automation", "Autopilot / Automation"
    NOTIFICATION = "notification", "Notification"
    SECURITY = "security", "Sécurité"
    SUPPORT = "support", "Support"
    OTHER = "other", "Autre"


class ModerationStatus(models.TextChoices):
    OPEN = "open", "Ouvert"
    REVIEWING = "reviewing", "En revue"
    ACTIONED = "actioned", "Action appliquée"
    DISMISSED = "dismissed", "Classé sans suite"


class ModerationTarget(models.TextChoices):
    ORGANIZATION = "organization", "Organisation"
    EVENT = "event", "Événement"


class WorkerState(models.TextChoices):
    HEALTHY = "healthy", "Opérationnel"
    DEGRADED = "degraded", "Dégradé"
    STOPPED = "stopped", "Arrêté"


class OperationsIncident(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=220)
    category = models.CharField(max_length=24, choices=IncidentCategory.choices)
    severity = models.CharField(
        max_length=16,
        choices=IncidentSeverity.choices,
        default=IncidentSeverity.MEDIUM,
    )
    status = models.CharField(
        max_length=20,
        choices=IncidentStatus.choices,
        default=IncidentStatus.OPEN,
    )
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.SET_NULL,
        related_name="operations_incidents",
        null=True,
        blank=True,
    )
    event = models.ForeignKey(
        "events.Event",
        on_delete=models.SET_NULL,
        related_name="operations_incidents",
        null=True,
        blank=True,
    )
    payment = models.ForeignKey(
        "payments.Payment",
        on_delete=models.SET_NULL,
        related_name="operations_incidents",
        null=True,
        blank=True,
    )
    scan_log = models.ForeignKey(
        "scanner.ScanLog",
        on_delete=models.SET_NULL,
        related_name="operations_incidents",
        null=True,
        blank=True,
    )
    description = models.TextField()
    resolution = models.TextField(blank=True)
    opened_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="operations_incidents_opened",
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="operations_incidents_assigned",
        null=True,
        blank=True,
    )
    detected_at = models.DateTimeField(default=timezone.now)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "severity", "created_at"], name="ops_inc_status_idx"),
            models.Index(fields=["organization", "status"], name="ops_inc_org_idx"),
            models.Index(fields=["event", "status"], name="ops_inc_event_idx"),
        ]

    def clean(self):
        super().clean()
        errors = {}
        self.title = (self.title or "").strip()
        self.resolution = (self.resolution or "").strip()
        if not self.title:
            errors["title"] = "Le titre est obligatoire."
        if self.status == IncidentStatus.RESOLVED and not self.resolution:
            errors["resolution"] = "Une résolution est requise pour clôturer l'incident comme résolu."
        if self.assigned_to_id and not self.assigned_to.is_staff:
            errors["assigned_to"] = "Un incident Operations ne peut être assigné qu'à un membre du staff Makolo."

        event_organization_id = self.event.organization_id if self.event_id else None
        payment_event_id = self.payment.order.event_id if self.payment_id else None
        payment_organization_id = self.payment.order.event.organization_id if self.payment_id else None
        scan_event_id = self.scan_log.event_id if self.scan_log_id else None
        scan_organization_id = self.scan_log.event.organization_id if self.scan_log_id else None

        if self.event_id and self.organization_id and event_organization_id:
            if event_organization_id != self.organization_id:
                errors["event"] = "L'événement doit appartenir à l'organisation de l'incident."
        if self.payment_id and self.event_id and payment_event_id != self.event_id:
            errors["payment"] = "Le paiement doit appartenir à l'événement de l'incident."
        if self.scan_log_id and self.event_id and scan_event_id != self.event_id:
            errors["scan_log"] = "Le scan doit appartenir à l'événement de l'incident."
        if self.payment_id and self.organization_id and payment_organization_id:
            if payment_organization_id != self.organization_id:
                errors["payment"] = "Le paiement doit appartenir à l'organisation de l'incident."
        if self.scan_log_id and self.organization_id and scan_organization_id:
            if scan_organization_id != self.organization_id:
                errors["scan_log"] = "Le scan doit appartenir à l'organisation de l'incident."
        if self.payment_id and self.scan_log_id and payment_event_id != scan_event_id:
            errors["scan_log"] = "Le scan et le paiement liés doivent appartenir au même événement."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.get_severity_display()} — {self.title}"


class ModerationCase(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    target_type = models.CharField(max_length=20, choices=ModerationTarget.choices)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.SET_NULL,
        related_name="moderation_cases",
        null=True,
        blank=True,
    )
    event = models.ForeignKey(
        "events.Event",
        on_delete=models.SET_NULL,
        related_name="moderation_cases",
        null=True,
        blank=True,
    )
    severity = models.CharField(
        max_length=16,
        choices=IncidentSeverity.choices,
        default=IncidentSeverity.MEDIUM,
    )
    status = models.CharField(
        max_length=20,
        choices=ModerationStatus.choices,
        default=ModerationStatus.OPEN,
    )
    reason = models.TextField()
    outcome = models.TextField(blank=True)
    opened_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="moderation_cases_opened",
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="moderation_cases_assigned",
        null=True,
        blank=True,
    )
    closed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "severity", "created_at"], name="ops_case_status_idx"),
            models.Index(fields=["target_type", "created_at"], name="ops_case_target_idx"),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.target_type == ModerationTarget.ORGANIZATION and not self.organization_id:
            errors["organization"] = "Une organisation est requise pour ce dossier."
        if self.target_type == ModerationTarget.EVENT and not self.event_id:
            errors["event"] = "Un événement est requis pour ce dossier."
        if self.event_id and self.organization_id and self.event.organization_id:
            if self.event.organization_id != self.organization_id:
                errors["event"] = "L'événement doit appartenir à l'organisation sélectionnée."
        if self.assigned_to_id and not self.assigned_to.is_staff:
            errors["assigned_to"] = "Le dossier ne peut être assigné qu'au staff Makolo."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.get_target_type_display()} — {self.get_status_display()}"


class OperationsAuditLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="operations_audit_actions",
        null=True,
        blank=True,
    )
    action = models.CharField(max_length=80)
    target_type = models.CharField(max_length=40)
    target_id = models.CharField(max_length=64)
    summary = models.CharField(max_length=255)
    before = models.JSONField(default=dict, blank=True)
    after = models.JSONField(default=dict, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["target_type", "target_id", "created_at"], name="ops_audit_target_idx"),
            models.Index(fields=["action", "created_at"], name="ops_audit_action_idx"),
        ]

    def __str__(self):
        return f"{self.action} — {self.target_type}:{self.target_id}"


class WorkerHeartbeat(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    worker_name = models.CharField(max_length=80)
    instance_id = models.CharField(max_length=120, default="default")
    state = models.CharField(max_length=16, choices=WorkerState.choices, default=WorkerState.HEALTHY)
    last_seen_at = models.DateTimeField(default=timezone.now)
    last_cycle_started_at = models.DateTimeField(null=True, blank=True)
    last_cycle_finished_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["worker_name", "instance_id"]
        constraints = [
            models.UniqueConstraint(fields=["worker_name", "instance_id"], name="ops_worker_instance_unique")
        ]
        indexes = [
            models.Index(fields=["state", "last_seen_at"], name="ops_worker_seen_idx"),
        ]

    def __str__(self):
        return f"{self.worker_name}:{self.instance_id} — {self.state}"
