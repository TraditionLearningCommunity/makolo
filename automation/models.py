import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from events.models import Event


class AutomationRunStatus(models.TextChoices):
    SUCCESS = "success", "Réussi"
    FAILED = "failed", "Échoué"
    SKIPPED = "skipped", "Ignoré"


class EventAutomationPolicy(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.OneToOneField(Event, on_delete=models.CASCADE, related_name="automation_policy")
    is_active = models.BooleanField(default=True)
    reminder_7d_enabled = models.BooleanField(default=False)
    reminder_24h_enabled = models.BooleanField(default=True)
    reminder_2h_enabled = models.BooleanField(default=True)
    post_event_followup_enabled = models.BooleanField(default=True)
    auto_complete_event = models.BooleanField(default=True)
    auto_close_sales_at_start = models.BooleanField(default=True)
    capacity_alerts_enabled = models.BooleanField(default=True)
    capacity_alert_percent = models.PositiveSmallIntegerField(default=80, validators=[MinValueValidator(1), MaxValueValidator(100)])
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
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="automation_runs", null=True, blank=True)
    rule_key = models.CharField(max_length=80)
    dedup_key = models.CharField(max_length=255, unique=True)
    status = models.CharField(max_length=16, choices=AutomationRunStatus.choices, default=AutomationRunStatus.SUCCESS)
    summary = models.CharField(max_length=255, blank=True)
    payload = models.JSONField(default=dict, blank=True)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["rule_key", "created_at"], name="automation_rule_ke_bdd6bd_idx"),
            models.Index(fields=["event", "created_at"], name="automation_event_i_a43472_idx"),
        ]

    def __str__(self):
        return f"{self.rule_key} — {self.status}"


class CRMWorkflowTrigger(models.TextChoices):
    FOLLOWED_ORGANIZER = "followed_organizer", "Nouvel abonné organisateur"
    ORDER_CONFIRMED = "order_confirmed", "Commande confirmée"
    ORDER_EXPIRED = "order_expired", "Commande expirée"
    WAITLIST_JOINED = "waitlist_joined", "Entrée en liste d’attente"
    CHECKED_IN = "checked_in", "Participant scanné / présent"
    BEFORE_EVENT = "before_event", "Avant le début d’un événement"
    EVENT_ENDED = "event_ended", "Après la fin d’un événement"
    NO_SHOW = "no_show", "Participant absent / no-show"
    BIRTHDAY = "birthday", "Anniversaire du contact"


class CRMWorkflowActionKind(models.TextChoices):
    SEND_EMAIL_TEMPLATE = "send_email_template", "Envoyer un modèle e-mail"
    IN_APP_NOTIFICATION = "in_app_notification", "Notification Makolo au contact"
    ADD_TAG = "add_tag", "Ajouter un tag CRM"
    REMOVE_TAG = "remove_tag", "Retirer un tag CRM"
    NOTIFY_TEAM = "notify_team", "Notifier l’équipe organisatrice"


class CRMWorkflowRunStatus(models.TextChoices):
    WAITING = "waiting", "En attente"
    RUNNING = "running", "En cours"
    COMPLETED = "completed", "Terminé"
    SKIPPED = "skipped", "Ignoré"
    FAILED = "failed", "Échoué"
    CANCELLED = "cancelled", "Annulé"


class CRMWorkflowActionRunStatus(models.TextChoices):
    QUEUED = "queued", "En attente"
    PROCESSING = "processing", "En cours"
    COMPLETED = "completed", "Terminé"
    SKIPPED = "skipped", "Ignoré"
    FAILED = "failed", "Échoué"


class CRMWorkflow(models.Model):
    """Parcours CRM organisationnel déclenché par un événement métier Makolo."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="crm_workflows",
    )
    name = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    trigger = models.CharField(max_length=32, choices=CRMWorkflowTrigger.choices)
    event = models.ForeignKey(
        "events.Event",
        on_delete=models.CASCADE,
        related_name="crm_workflows",
        null=True,
        blank=True,
    )
    segment = models.ForeignKey(
        "crm.AudienceSegment",
        on_delete=models.SET_NULL,
        related_name="automation_workflows",
        null=True,
        blank=True,
    )
    ticket_type = models.ForeignKey(
        "tickets.TicketType",
        on_delete=models.SET_NULL,
        related_name="crm_workflows",
        null=True,
        blank=True,
    )
    min_order_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=3, blank=True)
    event_offset_minutes = models.PositiveIntegerField(
        default=0,
        validators=[MaxValueValidator(525600)],
        help_text="Pour le déclencheur avant événement : nombre de minutes avant le début.",
    )
    trigger_grace_minutes = models.PositiveIntegerField(
        default=60,
        validators=[MinValueValidator(1), MaxValueValidator(10080)],
        help_text="Fenêtre pendant laquelle un déclencheur temporel reste valable.",
    )
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_crm_workflows",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["organization__name", "name"]
        constraints = [
            models.UniqueConstraint(fields=["organization", "name"], name="crm_workflow_org_name_unique")
        ]
        indexes = [
            models.Index(fields=["organization", "is_active", "trigger"], name="crm_wf_org_trigger_idx"),
            models.Index(fields=["event", "trigger", "is_active"], name="crm_wf_event_trigger_idx"),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.event_id and self.event.organization_id != self.organization_id:
            errors["event"] = "L’événement doit appartenir à la même organisation."
        if self.segment_id and self.segment.organization_id != self.organization_id:
            errors["segment"] = "Le segment doit appartenir à la même organisation."
        if self.ticket_type_id:
            if self.ticket_type.event.organization_id != self.organization_id:
                errors["ticket_type"] = "Le type de billet doit appartenir à la même organisation."
            if self.event_id and self.ticket_type.event_id != self.event_id:
                errors["ticket_type"] = "Le type de billet doit appartenir à l’événement sélectionné."
        if self.trigger in {CRMWorkflowTrigger.BEFORE_EVENT, CRMWorkflowTrigger.EVENT_ENDED, CRMWorkflowTrigger.NO_SHOW} and not self.event_id:
            errors["event"] = "Ce déclencheur nécessite un événement précis."
        if self.trigger == CRMWorkflowTrigger.BEFORE_EVENT and self.event_offset_minutes <= 0:
            errors["event_offset_minutes"] = "Indiquez un délai avant l’événement supérieur à zéro."
        if self.min_order_amount is not None and self.min_order_amount < 0:
            errors["min_order_amount"] = "Le montant minimum ne peut pas être négatif."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.currency = (self.currency or "").upper().strip()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.organization} — {self.name}"


class CRMWorkflowAction(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workflow = models.ForeignKey(CRMWorkflow, on_delete=models.CASCADE, related_name="actions")
    position = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])
    kind = models.CharField(max_length=32, choices=CRMWorkflowActionKind.choices)
    delay_minutes = models.PositiveIntegerField(
        default=0,
        validators=[MaxValueValidator(525600)],
        help_text="Délai après l’étape précédente.",
    )
    template = models.ForeignKey(
        "crm.CampaignTemplate",
        on_delete=models.PROTECT,
        related_name="automation_actions",
        null=True,
        blank=True,
    )
    tag = models.ForeignKey(
        "crm.CRMTag",
        on_delete=models.PROTECT,
        related_name="automation_actions",
        null=True,
        blank=True,
    )
    title = models.CharField(max_length=180, blank=True)
    message = models.TextField(blank=True)
    marketing_action = models.BooleanField(
        default=False,
        help_text="Pour une notification Makolo promotionnelle, exige le consentement marketing et les préférences de l’organisateur.",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["workflow", "position"]
        constraints = [
            models.UniqueConstraint(fields=["workflow", "position"], name="crm_workflow_action_position_unique")
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.kind == CRMWorkflowActionKind.SEND_EMAIL_TEMPLATE:
            if not self.template_id:
                errors["template"] = "Choisissez le modèle e-mail à envoyer."
            elif self.template.organization_id != self.workflow.organization_id:
                errors["template"] = "Le modèle doit appartenir à la même organisation."
            elif self.template.kind == "event_update" and not self.workflow.event_id and self.workflow.trigger in {
                CRMWorkflowTrigger.FOLLOWED_ORGANIZER,
                CRMWorkflowTrigger.BIRTHDAY,
            }:
                errors["template"] = "Une communication événementielle nécessite un contexte événement."
        if self.kind in {CRMWorkflowActionKind.ADD_TAG, CRMWorkflowActionKind.REMOVE_TAG}:
            if not self.tag_id:
                errors["tag"] = "Choisissez le tag CRM à modifier."
            elif self.tag.organization_id != self.workflow.organization_id:
                errors["tag"] = "Le tag doit appartenir à la même organisation."
        if self.kind in {CRMWorkflowActionKind.IN_APP_NOTIFICATION, CRMWorkflowActionKind.NOTIFY_TEAM}:
            if not self.title.strip():
                errors["title"] = "Le titre est obligatoire pour cette action."
            if not self.message.strip():
                errors["message"] = "Le message est obligatoire pour cette action."
        if self.marketing_action and self.kind != CRMWorkflowActionKind.IN_APP_NOTIFICATION:
            errors["marketing_action"] = "Ce réglage s’applique uniquement aux notifications Makolo destinées au contact."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.workflow.name} — #{self.position} {self.get_kind_display()}"


class CRMWorkflowRun(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workflow = models.ForeignKey(CRMWorkflow, on_delete=models.CASCADE, related_name="runs")
    contact = models.ForeignKey(
        "crm.CRMContact",
        on_delete=models.SET_NULL,
        related_name="automation_runs",
        null=True,
        blank=True,
    )
    event = models.ForeignKey(
        "events.Event",
        on_delete=models.SET_NULL,
        related_name="crm_workflow_runs",
        null=True,
        blank=True,
    )
    order = models.ForeignKey(
        "tickets.TicketOrder",
        on_delete=models.SET_NULL,
        related_name="crm_workflow_runs",
        null=True,
        blank=True,
    )
    ticket = models.ForeignKey(
        "tickets.Ticket",
        on_delete=models.SET_NULL,
        related_name="crm_workflow_runs",
        null=True,
        blank=True,
    )
    source_type = models.CharField(max_length=40)
    source_id = models.CharField(max_length=255)
    dedup_key = models.CharField(max_length=255, unique=True)
    status = models.CharField(max_length=16, choices=CRMWorkflowRunStatus.choices, default=CRMWorkflowRunStatus.WAITING)
    context = models.JSONField(default=dict, blank=True)
    skip_reason = models.CharField(max_length=255, blank=True)
    error = models.TextField(blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["workflow", "status", "created_at"], name="crm_wf_run_status_idx"),
            models.Index(fields=["contact", "created_at"], name="crm_wf_run_contact_idx"),
        ]

    def __str__(self):
        return f"{self.workflow.name} — {self.source_type}:{self.source_id}"


class CRMWorkflowActionRun(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    run = models.ForeignKey(CRMWorkflowRun, on_delete=models.CASCADE, related_name="action_runs")
    action = models.ForeignKey(CRMWorkflowAction, on_delete=models.PROTECT, related_name="runs")
    status = models.CharField(
        max_length=16,
        choices=CRMWorkflowActionRunStatus.choices,
        default=CRMWorkflowActionRunStatus.QUEUED,
    )
    scheduled_for = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    max_attempts = models.PositiveSmallIntegerField(default=3)
    output = models.JSONField(default=dict, blank=True)
    error = models.TextField(blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["scheduled_for", "created_at"]
        constraints = [
            models.UniqueConstraint(fields=["run", "action"], name="crm_workflow_action_run_unique")
        ]
        indexes = [
            models.Index(fields=["status", "scheduled_for"], name="crm_wf_action_due_idx"),
            models.Index(fields=["run", "status"], name="crm_wf_action_run_idx"),
        ]

    def __str__(self):
        return f"{self.run} — {self.action.position} — {self.status}"
