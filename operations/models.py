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
    severity = models.CharField(max_length=16, choices=IncidentSeverity.choices, default=IncidentSeverity.MEDIUM)
    status = models.CharField(max_length=20, choices=IncidentStatus.choices, default=IncidentStatus.OPEN)
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.SET_NULL,
        related_name="operations_incidents", null=True, blank=True,
    )
    activity = models.ForeignKey(
        "activities.Activity", on_delete=models.PROTECT,
        related_name="operations_incidents", null=True, blank=True,
    )
    occurrence = models.ForeignKey(
        "activities.Occurrence", on_delete=models.PROTECT,
        related_name="operations_incidents", null=True, blank=True,
    )
    event = models.ForeignKey(
        "events.Event", on_delete=models.SET_NULL,
        related_name="operations_incidents", null=True, blank=True,
        help_text="Projection Events historique; Operations utilise Activity/Occurrence comme contexte canonique.",
    )
    payment = models.ForeignKey(
        "payments.Payment", on_delete=models.SET_NULL,
        related_name="operations_incidents", null=True, blank=True,
    )
    scan_log = models.ForeignKey(
        "scanner.ScanLog", on_delete=models.SET_NULL,
        related_name="operations_incidents", null=True, blank=True,
    )
    description = models.TextField()
    resolution = models.TextField(blank=True)
    opened_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="operations_incidents_opened",
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        related_name="operations_incidents_assigned", null=True, blank=True,
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
            models.Index(fields=["activity", "status"], name="ops_inc_activity_idx"),
            models.Index(fields=["occurrence", "status"], name="ops_inc_occurrence_idx"),
            models.Index(fields=["event", "status"], name="ops_inc_event_idx"),
        ]

    def _payment_scope(self):
        if not self.payment_id:
            return None, None
        payment = self.payment
        if payment.commerce_order_id:
            journey = payment.commerce_order.journey
            return journey.activity, journey.occurrence
        if payment.order_id:
            event = payment.order.event
            activity = getattr(event, "activity", None)
            if activity is None:
                return None, None
            occurrence = activity.occurrences.filter(
                start_at=event.start_at, end_at=event.end_at
            ).order_by("id").first()
            return activity, occurrence
        return None, None

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

        if self.occurrence_id and not self.activity_id:
            self.activity_id = self.occurrence.activity_id
        if self.event_id and not self.activity_id and self.event.activity_id:
            self.activity_id = self.event.activity_id
        if self.activity_id and not self.organization_id and self.activity.space_id:
            self.organization_id = self.activity.space_id

        if self.occurrence_id and self.activity_id and self.occurrence.activity_id != self.activity_id:
            errors["occurrence"] = "L’Occurrence doit appartenir à l’Activity de l’incident."
        if self.activity_id and self.organization_id and self.activity.space_id:
            if self.activity.space_id != self.organization_id:
                errors["activity"] = "L’Activity doit appartenir à l’Espace de l’incident."
        if self.event_id and self.activity_id and self.event.activity_id:
            if self.event.activity_id != self.activity_id:
                errors["event"] = "L’Event projette une autre Activity que l’incident."
        if self.event_id and self.organization_id and self.event.organization_id:
            if self.event.organization_id != self.organization_id:
                errors["event"] = "L’événement doit appartenir à l’Espace de l’incident."

        payment_activity, payment_occurrence = self._payment_scope()
        if payment_activity is not None:
            if self.activity_id and payment_activity.pk != self.activity_id:
                errors["payment"] = "Le paiement appartient à une autre Activity."
            if self.organization_id and payment_activity.space_id and payment_activity.space_id != self.organization_id:
                errors["payment"] = "Le paiement appartient à un autre Espace."
            if self.occurrence_id and payment_occurrence is not None and payment_occurrence.pk != self.occurrence_id:
                errors["payment"] = "Le paiement appartient à une autre Occurrence."

        if self.scan_log_id:
            scan_event = self.scan_log.event
            scan_activity_id = scan_event.activity_id
            if self.activity_id and scan_activity_id and scan_activity_id != self.activity_id:
                errors["scan_log"] = "Le scan appartient à une autre Activity."
            if self.organization_id and scan_event.organization_id and scan_event.organization_id != self.organization_id:
                errors["scan_log"] = "Le scan appartient à un autre Espace."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.get_severity_display()} — {self.title}"


class ModerationCase(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    target_type = models.CharField(max_length=20, choices=ModerationTarget.choices)
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.SET_NULL,
        related_name="moderation_cases", null=True, blank=True,
    )
    event = models.ForeignKey(
        "events.Event", on_delete=models.SET_NULL,
        related_name="moderation_cases", null=True, blank=True,
    )
    severity = models.CharField(max_length=16, choices=IncidentSeverity.choices, default=IncidentSeverity.MEDIUM)
    status = models.CharField(max_length=20, choices=ModerationStatus.choices, default=ModerationStatus.OPEN)
    reason = models.TextField()
    outcome = models.TextField(blank=True)
    opened_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="moderation_cases_opened",
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        related_name="moderation_cases_assigned", null=True, blank=True,
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
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        related_name="operations_audit_actions", null=True, blank=True,
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
        indexes = [models.Index(fields=["state", "last_seen_at"], name="ops_worker_seen_idx")]

    def __str__(self):
        return f"{self.worker_name}:{self.instance_id} — {self.state}"
