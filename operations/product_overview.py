from datetime import timedelta

from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.utils import timezone

from automation.models import (
    AutomationRun,
    AutomationRunStatus,
    CRMWorkflowActionRun,
    CRMWorkflowActionRunStatus,
)
from events.models import Event, EventStatus
from notifications.models import DeliveryStatus, NotificationDelivery
from organizations.models import Organization, OrganizationVerificationStatus
from payments.models import Payment, PaymentEvent, PaymentStatus, Refund, RefundStatus
from scanner.models import ScanLog, ScanResult

from .models import (
    IncidentSeverity,
    IncidentStatus,
    OperationsAuditLog,
    OperationsIncident,
    WorkerHeartbeat,
    WorkerState,
)
from .permissions import user_can_access_operations


DEMO_SEED = "makolo-demo"
TERMINAL_INCIDENT_STATUSES = {IncidentStatus.RESOLVED, IncidentStatus.DISMISSED}


def _without_demo_seed(queryset, json_prefix="metadata"):
    """Keep records without a demo marker, including rows where the key is absent.

    The explicit is-null branch matters on SQLite because negating a JSON key
    comparison alone does not reliably retain objects whose key is missing.
    """
    lookup = f"{json_prefix}__seed"
    return queryset.filter(
        Q(**{f"{lookup}__isnull": True}) | ~Q(**{lookup: DEMO_SEED})
    )


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


def build_product_operations_overview(user):
    """Build Operations health from real records while retaining demo history.

    Demo rows remain in their source tables and dedicated history pages. They
    are simply excluded from the health calculation whenever the seed marker is
    present, so a demonstration scenario cannot masquerade as a production
    outage.
    """
    if not user_can_access_operations(user):
        raise PermissionDenied("Le Makolo Operations Center est réservé au staff plateforme.")

    now = timezone.now()
    since_24h = now - timedelta(hours=24)
    since_15m = now - timedelta(minutes=15)
    stale_webhook_before = now - timedelta(minutes=10)
    stale_queue_before = now - timedelta(minutes=15)
    stale_worker_before = now - timedelta(minutes=2)

    incidents = _without_demo_seed(OperationsIncident.objects.all())
    open_incidents = incidents.exclude(status__in=list(TERMINAL_INCIDENT_STATUSES))
    critical_incidents = open_incidents.filter(severity=IncidentSeverity.CRITICAL).count()

    organizations = _without_demo_seed(Organization.objects.all(), "created_by__metadata")
    pending_orgs = organizations.filter(
        verification_status__in=[
            OrganizationVerificationStatus.NEW,
            OrganizationVerificationStatus.PENDING,
        ]
    )
    suspended_orgs = organizations.filter(
        verification_status=OrganizationVerificationStatus.SUSPENDED
    ).count()

    payments = _without_demo_seed(Payment.objects.all())
    recent_payments = payments.filter(created_at__gte=since_24h)
    payment_attempts = recent_payments.count()
    failed_payments = recent_payments.filter(status=PaymentStatus.FAILED).count()
    pending_payments = payments.filter(
        status__in=[PaymentStatus.PENDING, PaymentStatus.PROCESSING],
        created_at__lt=stale_queue_before,
    ).count()
    payment_failure_rate = (
        round((failed_payments / payment_attempts) * 100, 1) if payment_attempts else 0.0
    )

    payment_events = _without_demo_seed(PaymentEvent.objects.all(), "payment__metadata")
    invalid_webhooks = payment_events.filter(
        received_at__gte=since_24h,
        signature_valid=False,
    ).count()
    stuck_webhooks = payment_events.filter(
        processed=False,
        received_at__lt=stale_webhook_before,
    ).count()
    failed_refunds = _without_demo_seed(
        Refund.objects.all(), "payment__metadata"
    ).filter(
        status=RefundStatus.FAILED,
        created_at__gte=since_24h,
    ).count()

    scans = _without_demo_seed(ScanLog.objects.all())
    recent_scans = scans.filter(scanned_at__gte=since_15m)
    scan_total = recent_scans.count()
    rejected_scans = recent_scans.exclude(result=ScanResult.ACCEPTED).count()
    duplicate_scans = recent_scans.filter(result=ScanResult.DUPLICATE).count()
    invalid_scans = recent_scans.filter(
        result__in=[
            ScanResult.INVALID_TOKEN,
            ScanResult.UNKNOWN_TICKET,
            ScanResult.WRONG_EVENT,
        ]
    ).count()
    scan_rejection_rate = (
        round((rejected_scans / scan_total) * 100, 1) if scan_total else 0.0
    )

    automation_runs = _without_demo_seed(AutomationRun.objects.all(), "payload")
    automation_failures = automation_runs.filter(
        status=AutomationRunStatus.FAILED,
        created_at__gte=since_24h,
    ).count()
    crm_action_runs = _without_demo_seed(CRMWorkflowActionRun.objects.all(), "output")
    crm_action_failures = crm_action_runs.filter(
        status=CRMWorkflowActionRunStatus.FAILED,
        updated_at__gte=since_24h,
    ).count()
    overdue_crm_actions = crm_action_runs.filter(
        status__in=[
            CRMWorkflowActionRunStatus.QUEUED,
            CRMWorkflowActionRunStatus.PROCESSING,
        ],
        scheduled_for__lt=stale_queue_before,
    ).count()

    deliveries = _without_demo_seed(
        NotificationDelivery.objects.all(), "notification__metadata"
    )
    failed_deliveries = deliveries.filter(
        status=DeliveryStatus.FAILED,
        updated_at__gte=since_24h,
    ).count()
    overdue_deliveries = deliveries.filter(
        status__in=[DeliveryStatus.QUEUED, DeliveryStatus.PROCESSING],
        scheduled_for__lt=stale_queue_before,
    ).count()

    workers = _without_demo_seed(WorkerHeartbeat.objects.all())
    stale_workers = workers.filter(last_seen_at__lt=stale_worker_before).exclude(
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
        signals.append(_signal("verification_queue", "medium", "moderation", "Organisations à vérifier", "La file de vérification contient des organisations réelles nouvelles ou en attente.", pending_orgs.count(), "/operations/organizations/"))

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
        .values(
            "id",
            "slug",
            "name",
            "verification_status",
            "created_at",
            "event_count",
            "member_count",
        )[:12]
    )
    incident_rows = list(
        open_incidents.order_by("-created_at").values(
            "id",
            "title",
            "category",
            "severity",
            "status",
            "organization_id",
            "event_id",
            "created_at",
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
            "stale": heartbeat.last_seen_at < stale_worker_before
            and heartbeat.state != WorkerState.STOPPED,
        }
        for heartbeat in workers
    ]
    recent_audit = list(
        _without_demo_seed(OperationsAuditLog.objects.all())
        .values("id", "action", "target_type", "target_id", "summary", "created_at")[:12]
    )

    demo_summary = {
        "incidents": OperationsIncident.objects.filter(metadata__seed=DEMO_SEED).count(),
        "workers": WorkerHeartbeat.objects.filter(metadata__seed=DEMO_SEED).count(),
        "payments": Payment.objects.filter(metadata__seed=DEMO_SEED).count(),
        "scans": ScanLog.objects.filter(metadata__seed=DEMO_SEED).count(),
        "notification_deliveries": NotificationDelivery.objects.filter(
            notification__metadata__seed=DEMO_SEED
        ).count(),
        "events": Event.objects.filter(metadata__seed=DEMO_SEED).count(),
    }
    demo_data_present = any(demo_summary.values())

    return {
        "health": health,
        "generated_at": now,
        "demo_data_present": demo_data_present,
        "demo_summary": demo_summary,
        "metrics": {
            "open_incidents": open_incidents.count(),
            "critical_incidents": critical_incidents,
            "pending_organizations": pending_orgs.count(),
            "suspended_organizations": suspended_orgs,
            "published_events": _without_demo_seed(Event.objects.all()).filter(status=EventStatus.PUBLISHED).count(),
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
