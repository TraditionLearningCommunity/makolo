from datetime import timedelta

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from automation.models import (
    AutomationRun,
    AutomationRunStatus,
    CRMWorkflowActionRun,
    CRMWorkflowActionRunStatus,
)
from events.models import Event, EventStatus, EventVisibility
from notifications.models import DeliveryStatus, NotificationDelivery
from organizations.models import Organization, OrganizationVerificationStatus
from payments.models import Payment, PaymentEvent, PaymentStatus, Refund, RefundStatus
from scanner.models import ScanLog, ScanResult

from .models import (
    IncidentSeverity,
    IncidentStatus,
    ModerationCase,
    ModerationStatus,
    ModerationTarget,
    OperationsAuditLog,
    OperationsIncident,
    WorkerHeartbeat,
    WorkerState,
)
from .permissions import user_can_access_operations


TERMINAL_INCIDENT_STATUSES = {IncidentStatus.RESOLVED, IncidentStatus.DISMISSED}
_UNSET = object()


def _require_staff(user):
    if not user_can_access_operations(user):
        raise PermissionDenied("Le Makolo Operations Center est réservé au staff plateforme.")


def _snapshot_organization(organization):
    return {
        "id": str(organization.pk),
        "verification_status": organization.verification_status,
        "public_profile": organization.public_profile,
    }


def _snapshot_event(event):
    return {
        "id": str(event.pk),
        "status": event.status,
        "visibility": event.visibility,
        "cancelled_at": event.cancelled_at.isoformat() if event.cancelled_at else None,
    }


def audit_action(*, actor, action, target_type, target_id, summary, before=None, after=None, metadata=None):
    return OperationsAuditLog.objects.create(
        actor=actor,
        action=action,
        target_type=target_type,
        target_id=str(target_id),
        summary=summary,
        before=before or {},
        after=after or {},
        metadata=metadata or {},
    )


@transaction.atomic
def change_organization_verification(*, organization, status, actor, reason):
    _require_staff(actor)
    reason = (reason or "").strip()
    valid_statuses = {value for value, _label in OrganizationVerificationStatus.choices}
    if status not in valid_statuses:
        raise ValidationError({"status": "Statut de vérification invalide."})
    if not reason:
        raise ValidationError({"reason": "Une justification Operations est obligatoire."})

    organization = Organization.objects.select_for_update().get(pk=organization.pk)
    before = _snapshot_organization(organization)
    organization.verification_status = status
    organization.save(update_fields=["verification_status", "updated_at"])
    after = _snapshot_organization(organization)

    ModerationCase.objects.create(
        target_type=ModerationTarget.ORGANIZATION,
        organization=organization,
        severity=(IncidentSeverity.HIGH if status == OrganizationVerificationStatus.SUSPENDED else IncidentSeverity.MEDIUM),
        status=ModerationStatus.ACTIONED,
        reason=reason,
        outcome=f"Statut de vérification défini sur {organization.get_verification_status_display()}.",
        opened_by=actor,
        assigned_to=actor,
        closed_at=timezone.now(),
    )
    audit_action(
        actor=actor,
        action="organization.verification_changed",
        target_type="organization",
        target_id=organization.pk,
        summary=f"Statut de {organization.name} → {organization.get_verification_status_display()}",
        before=before,
        after=after,
        metadata={"reason": reason},
    )
    return organization


@transaction.atomic
def moderate_event(*, event, action, actor, reason):
    _require_staff(actor)
    reason = (reason or "").strip()
    if not reason:
        raise ValidationError({"reason": "Une justification Operations est obligatoire."})
    allowed = {"unlist", "private", "cancel", "restore_public"}
    if action not in allowed:
        raise ValidationError({"action": "Action de modération invalide."})

    event = type(event).objects.select_for_update().get(pk=event.pk)
    before = _snapshot_event(event)
    now = timezone.now()
    if action == "unlist":
        event.visibility = EventVisibility.UNLISTED
        fields = ["visibility", "updated_at"]
        outcome = "Événement retiré de la découverte publique."
    elif action == "private":
        event.visibility = EventVisibility.PRIVATE
        fields = ["visibility", "updated_at"]
        outcome = "Événement rendu privé."
    elif action == "cancel":
        event.status = EventStatus.CANCELLED
        event.cancelled_at = event.cancelled_at or now
        fields = ["status", "cancelled_at", "updated_at"]
        outcome = "Événement annulé par Operations."
    else:
        event.visibility = EventVisibility.PUBLIC
        fields = ["visibility", "updated_at"]
        outcome = "Visibilité publique restaurée sans changer le statut métier."
    event.save(update_fields=fields)
    after = _snapshot_event(event)

    ModerationCase.objects.create(
        target_type=ModerationTarget.EVENT,
        organization=event.organization,
        event=event,
        severity=IncidentSeverity.HIGH if action == "cancel" else IncidentSeverity.MEDIUM,
        status=ModerationStatus.ACTIONED,
        reason=reason,
        outcome=outcome,
        opened_by=actor,
        assigned_to=actor,
        closed_at=now,
    )
    audit_action(
        actor=actor,
        action=f"event.moderation.{action}",
        target_type="event",
        target_id=event.pk,
        summary=f"Modération de {event.title}: {outcome}",
        before=before,
        after=after,
        metadata={"reason": reason},
    )
    return event


@transaction.atomic
def create_incident(*, actor, **data):
    _require_staff(actor)
    incident = OperationsIncident(opened_by=actor, **data)
    incident.full_clean()
    incident.save()
    audit_action(
        actor=actor,
        action="incident.created",
        target_type="operations_incident",
        target_id=incident.pk,
        summary=f"Incident créé: {incident.title}",
        after={"status": incident.status, "severity": incident.severity, "category": incident.category},
    )
    return incident


@transaction.atomic
def update_incident(
    *,
    incident,
    actor,
    status=None,
    severity=None,
    assigned_to=_UNSET,
    resolution=None,
):
    _require_staff(actor)
    incident = OperationsIncident.objects.select_for_update().get(pk=incident.pk)
    before = {
        "status": incident.status,
        "severity": incident.severity,
        "assigned_to": str(incident.assigned_to_id) if incident.assigned_to_id else None,
        "resolved_at": incident.resolved_at.isoformat() if incident.resolved_at else None,
    }
    now = timezone.now()
    if status is not None:
        valid_statuses = {value for value, _label in IncidentStatus.choices}
        if status not in valid_statuses:
            raise ValidationError({"status": "Statut d'incident invalide."})
        incident.status = status
        if status in {IncidentStatus.INVESTIGATING, IncidentStatus.MONITORING} and not incident.acknowledged_at:
            incident.acknowledged_at = now
        if status in TERMINAL_INCIDENT_STATUSES:
            incident.resolved_at = incident.resolved_at or now
        else:
            incident.resolved_at = None
    if severity is not None:
        valid_severities = {value for value, _label in IncidentSeverity.choices}
        if severity not in valid_severities:
            raise ValidationError({"severity": "Sévérité invalide."})
        incident.severity = severity
    if assigned_to is not _UNSET:
        incident.assigned_to = assigned_to
    if resolution is not None:
        incident.resolution = resolution.strip()
    incident.full_clean()
    incident.save()
    after = {
        "status": incident.status,
        "severity": incident.severity,
        "assigned_to": str(incident.assigned_to_id) if incident.assigned_to_id else None,
        "resolved_at": incident.resolved_at.isoformat() if incident.resolved_at else None,
    }
    audit_action(
        actor=actor,
        action="incident.updated",
        target_type="operations_incident",
        target_id=incident.pk,
        summary=f"Incident mis à jour: {incident.title}",
        before=before,
        after=after,
    )
    return incident


def record_worker_heartbeat(
    *,
    worker_name,
    instance_id="default",
    state=WorkerState.HEALTHY,
    last_error="",
    metadata=None,
    cycle_started=False,
    cycle_finished=False,
):
    now = timezone.now()
    defaults = {
        "state": state,
        "last_seen_at": now,
        "last_error": (last_error or "")[:4000],
        "metadata": metadata or {},
    }
    if cycle_started:
        defaults["last_cycle_started_at"] = now
    if cycle_finished:
        defaults["last_cycle_finished_at"] = now
    heartbeat, _created = WorkerHeartbeat.objects.update_or_create(
        worker_name=worker_name,
        instance_id=instance_id,
        defaults=defaults,
    )
    return heartbeat


def _signal(code, severity, domain, title, detail, count=0, action_url=""):
    return {
        "code": code,
        "severity": severity,
        "domain": domain,
        "title": title,
        "detail": detail,
        "count": count,
        "action_url": action_url,
    }


def build_operations_overview(user):
    _require_staff(user)
    now = timezone.now()
    since_24h = now - timedelta(hours=24)
    since_15m = now - timedelta(minutes=15)
    stale_webhook_before = now - timedelta(minutes=10)
    stale_queue_before = now - timedelta(minutes=15)
    stale_worker_before = now - timedelta(minutes=2)

    open_incident_filter = ~Q(status__in=list(TERMINAL_INCIDENT_STATUSES))
    open_incidents = OperationsIncident.objects.filter(open_incident_filter)
    critical_incidents = open_incidents.filter(severity=IncidentSeverity.CRITICAL).count()

    pending_orgs = Organization.objects.filter(
        verification_status__in=[OrganizationVerificationStatus.NEW, OrganizationVerificationStatus.PENDING]
    )
    suspended_orgs = Organization.objects.filter(
        verification_status=OrganizationVerificationStatus.SUSPENDED
    ).count()

    recent_payments = Payment.objects.filter(created_at__gte=since_24h)
    payment_attempts = recent_payments.count()
    failed_payments = recent_payments.filter(status=PaymentStatus.FAILED).count()
    pending_payments = Payment.objects.filter(
        status__in=[PaymentStatus.PENDING, PaymentStatus.PROCESSING],
        created_at__lt=stale_queue_before,
    ).count()
    payment_failure_rate = round((failed_payments / payment_attempts) * 100, 1) if payment_attempts else 0.0
    invalid_webhooks = PaymentEvent.objects.filter(
        received_at__gte=since_24h,
        signature_valid=False,
    ).count()
    stuck_webhooks = PaymentEvent.objects.filter(
        processed=False,
        received_at__lt=stale_webhook_before,
    ).count()
    failed_refunds = Refund.objects.filter(
        status=RefundStatus.FAILED,
        created_at__gte=since_24h,
    ).count()

    recent_scans = ScanLog.objects.filter(scanned_at__gte=since_15m)
    scan_total = recent_scans.count()
    rejected_scans = recent_scans.exclude(result=ScanResult.ACCEPTED).count()
    duplicate_scans = recent_scans.filter(result=ScanResult.DUPLICATE).count()
    invalid_scans = recent_scans.filter(
        result__in=[ScanResult.INVALID_TOKEN, ScanResult.UNKNOWN_TICKET, ScanResult.WRONG_EVENT]
    ).count()
    scan_rejection_rate = round((rejected_scans / scan_total) * 100, 1) if scan_total else 0.0

    automation_failures = AutomationRun.objects.filter(
        status=AutomationRunStatus.FAILED,
        created_at__gte=since_24h,
    ).count()
    crm_action_failures = CRMWorkflowActionRun.objects.filter(
        status=CRMWorkflowActionRunStatus.FAILED,
        updated_at__gte=since_24h,
    ).count()
    overdue_crm_actions = CRMWorkflowActionRun.objects.filter(
        status__in=[CRMWorkflowActionRunStatus.QUEUED, CRMWorkflowActionRunStatus.PROCESSING],
        scheduled_for__lt=stale_queue_before,
    ).count()
    failed_deliveries = NotificationDelivery.objects.filter(
        status=DeliveryStatus.FAILED,
        updated_at__gte=since_24h,
    ).count()
    overdue_deliveries = NotificationDelivery.objects.filter(
        status__in=[DeliveryStatus.QUEUED, DeliveryStatus.PROCESSING],
        scheduled_for__lt=stale_queue_before,
    ).count()

    stale_workers = WorkerHeartbeat.objects.filter(last_seen_at__lt=stale_worker_before).exclude(
        state=WorkerState.STOPPED
    )
    stale_worker_count = stale_workers.count()

    signals = []
    if critical_incidents:
        signals.append(_signal("critical_incidents", "critical", "incidents", "Incidents critiques ouverts", "Des incidents critiques nécessitent une prise en charge immédiate.", critical_incidents, "/operations/incidents/"))
    if invalid_webhooks:
        signals.append(_signal("invalid_webhooks", "critical", "payments", "Signatures webhook invalides", "Des événements de paiement ont été reçus avec une signature invalide. Aucun payload brut n'est exposé ici.", invalid_webhooks, "/operations/"))
    if stuck_webhooks:
        signals.append(_signal("stuck_webhooks", "high", "payments", "Webhooks non traités", "Des événements de paiement restent non traités au-delà de 10 minutes.", stuck_webhooks, "/operations/"))
    if payment_attempts >= 5 and payment_failure_rate >= 30:
        signals.append(_signal("payment_failure_rate", "high", "payments", "Taux d'échec paiement élevé", f"{payment_failure_rate}% des tentatives des dernières 24 h ont échoué.", failed_payments, "/operations/"))
    if pending_payments:
        signals.append(_signal("stale_payments", "medium", "payments", "Paiements bloqués", "Des paiements pending/processing dépassent 15 minutes.", pending_payments, "/operations/"))
    if failed_refunds:
        signals.append(_signal("failed_refunds", "high", "payments", "Remboursements en échec", "Des remboursements ont échoué dans les dernières 24 h.", failed_refunds, "/operations/"))
    if scan_total >= 10 and scan_rejection_rate >= 30:
        signals.append(_signal("scan_rejection_rate", "high", "access", "Taux de refus scanner élevé", f"{scan_rejection_rate}% des scans des 15 dernières minutes ont été refusés.", rejected_scans, "/operations/"))
    if invalid_scans >= 5:
        signals.append(_signal("invalid_scans", "high", "access", "Scans invalides répétés", "Plusieurs QR invalides, inconnus ou associés au mauvais événement ont été présentés.", invalid_scans, "/operations/"))
    if automation_failures or crm_action_failures:
        signals.append(_signal("automation_failures", "high", "automation", "Échecs d'automatisation", "Autopilot ou CRM Workflow a enregistré des échecs dans les dernières 24 h.", automation_failures + crm_action_failures, "/operations/"))
    if overdue_crm_actions:
        signals.append(_signal("overdue_crm", "medium", "automation", "Actions CRM en retard", "Des actions CRM sont toujours en attente après leur échéance.", overdue_crm_actions, "/operations/"))
    if failed_deliveries:
        signals.append(_signal("notification_failures", "high", "notifications", "Livraisons de notifications en échec", "Des livraisons e-mail/SMS/push ont échoué dans les dernières 24 h.", failed_deliveries, "/operations/"))
    if overdue_deliveries:
        signals.append(_signal("notification_backlog", "medium", "notifications", "File de notifications en retard", "Des livraisons restent en attente plus de 15 minutes.", overdue_deliveries, "/operations/"))
    if stale_worker_count:
        signals.append(_signal("stale_workers", "critical", "workers", "Worker sans heartbeat", "Un worker déclaré actif n'a plus émis de heartbeat depuis plus de 2 minutes.", stale_worker_count, "/operations/"))
    if pending_orgs.exists():
        signals.append(_signal("verification_queue", "medium", "moderation", "Organisations à vérifier", "La file de vérification contient des organisations nouvelles ou en attente.", pending_orgs.count(), "/operations/organizations/"))

    severity_rank = {"critical": 4, "high": 3, "medium": 2, "low": 1}
    signals.sort(key=lambda row: (-severity_rank[row["severity"]], row["domain"], row["code"]))
    if any(row["severity"] == "critical" for row in signals):
        health = "critical"
    elif any(row["severity"] == "high" for row in signals):
        health = "degraded"
    else:
        health = "healthy"

    org_queue = list(
        pending_orgs.annotate(
            event_count=Count("events", distinct=True),
            member_count=Count("memberships", distinct=True),
        )
        .order_by("created_at")
        .values("id", "slug", "name", "verification_status", "created_at", "event_count", "member_count")[:12]
    )

    incident_rows = list(
        open_incidents.order_by("-created_at").values(
            "id", "title", "category", "severity", "status", "organization_id", "event_id", "created_at"
        )[:12]
    )
    worker_rows = [
        {
            "id": heartbeat.pk,
            "worker_name": heartbeat.worker_name,
            "instance_id": heartbeat.instance_id,
            "state": heartbeat.state,
            "last_seen_at": heartbeat.last_seen_at,
            "last_error": heartbeat.last_error[:300],
            "stale": heartbeat.last_seen_at < stale_worker_before and heartbeat.state != WorkerState.STOPPED,
        }
        for heartbeat in WorkerHeartbeat.objects.all()
    ]
    recent_audit = list(
        OperationsAuditLog.objects.values(
            "id", "action", "target_type", "target_id", "summary", "created_at"
        )[:12]
    )

    return {
        "health": health,
        "generated_at": now,
        "metrics": {
            "open_incidents": open_incidents.count(),
            "critical_incidents": critical_incidents,
            "pending_organizations": pending_orgs.count(),
            "suspended_organizations": suspended_orgs,
            "published_events": Event.objects.filter(status=EventStatus.PUBLISHED).count(),
            "payment_attempts_24h": payment_attempts,
            "failed_payments_24h": failed_payments,
            "payment_failure_rate_24h": payment_failure_rate,
            "stale_payments": pending_payments,
            "invalid_webhooks_24h": invalid_webhooks,
            "stuck_webhooks": stuck_webhooks,
            "failed_refunds_24h": failed_refunds,
            "scans_15m": scan_total,
            "rejected_scans_15m": rejected_scans,
            "duplicate_scans_15m": duplicate_scans,
            "invalid_scans_15m": invalid_scans,
            "scan_rejection_rate_15m": scan_rejection_rate,
            "automation_failures_24h": automation_failures + crm_action_failures,
            "overdue_crm_actions": overdue_crm_actions,
            "failed_deliveries_24h": failed_deliveries,
            "overdue_deliveries": overdue_deliveries,
            "stale_workers": stale_worker_count,
        },
        "signals": signals,
        "organization_queue": org_queue,
        "incidents": incident_rows,
        "workers": worker_rows,
        "recent_audit": recent_audit,
    }
