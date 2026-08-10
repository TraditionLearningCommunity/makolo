from __future__ import annotations

import hashlib
from datetime import timedelta

from operations.models import (
    IncidentCategory,
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
from payments.models import PaymentStatus, Refund, RefundStatus
from scanner.models import ScanLog, ScanResult
from tickets.models import TicketStatus

from .common import SeedContext, backdate, choose, upsert


def seed_operations_and_edge_cases(ctx: SeedContext) -> None:
    _ensure_edge_cases(ctx)
    _seed_operations(ctx)


def _ensure_edge_cases(ctx: SeedContext) -> None:
    if not Refund.objects.exists():
        payment = next((p for p in ctx.payments if p.status == PaymentStatus.SUCCEEDED and p.amount > 0), None)
        if payment:
            payment.status = PaymentStatus.REFUNDED
            payment.save(update_fields=["status"])
            for ticket in payment.order.tickets.all():
                ticket.status = TicketStatus.REFUNDED
                ticket.save(update_fields=["status"])
            refund = upsert(Refund, "guaranteed-demo-refund", defaults={
                "reference": "RFD-DEMO-GUARANTEED",
                "payment": payment,
                "requested_by": ctx.staff_users[1],
                "status": RefundStatus.SUCCEEDED,
                "amount": payment.amount,
                "currency": payment.currency,
                "reason": "Remboursement complet garanti par le jeu de démonstration.",
                "provider_reference": "SBX-RFD-GUARANTEED",
                "idempotency_key": "demo-refund-guaranteed",
                "failure_message": "",
                "processed_at": ctx.as_of - timedelta(days=4),
            })
            backdate(refund, created_at=ctx.as_of - timedelta(days=4), updated_at=ctx.as_of - timedelta(days=4))

    event = next((e for e in ctx.events if e.access_gates.exists()), None)
    if event:
        assignment = event.scanner_assignments.first()
        gate = event.access_gates.first()
        scanner = assignment.agent
        base_time = min(ctx.as_of - timedelta(days=2), event.end_at - timedelta(minutes=5))
        refusal_specs = [
            (ScanResult.INVALID_TOKEN, "QR illisible ou signature invalide.", None),
            (ScanResult.UNKNOWN_TICKET, "Billet introuvable.", None),
            (ScanResult.EVENT_UNAVAILABLE, "Événement indisponible.", None),
            (ScanResult.GATE_UNAVAILABLE, "Porte temporairement indisponible.", None),
        ]
        for i, (result, message, ticket) in enumerate(refusal_specs):
            upsert(ScanLog, f"edge-scan-{result}", defaults={
                "event": event,
                "ticket": ticket,
                "scanner": scanner,
                "assignment": assignment,
                "access_gate": gate,
                "result": result,
                "message": message,
                "qr_fingerprint": hashlib.sha256(f"demo-{result}".encode()).hexdigest(),
                "client_reference": f"EDGE-{result[:10].upper()}-{i}",
                "gate": gate.name,
                "metadata": {"seed": "makolo-demo", "scenario": result},
                "scanned_at": base_time + timedelta(minutes=i),
            })

        other_ticket = next((t for t in ctx.tickets if t.event_id != event.id), None)
        if other_ticket:
            upsert(ScanLog, "edge-scan-wrong-event", defaults={
                "event": event,
                "ticket": other_ticket,
                "scanner": scanner,
                "assignment": assignment,
                "access_gate": gate,
                "result": ScanResult.WRONG_EVENT,
                "message": "Ce billet appartient à un autre événement.",
                "qr_fingerprint": hashlib.sha256(other_ticket.qr_token.encode()).hexdigest(),
                "client_reference": "EDGE-WRONG-EVENT",
                "gate": gate.name,
                "metadata": {"seed": "makolo-demo", "scenario": "wrong_event"},
                "scanned_at": base_time + timedelta(minutes=8),
            })


def _seed_operations(ctx: SeedContext) -> None:
    staff = ctx.staff_users
    categories = list(IncidentCategory.values)
    severities = list(IncidentSeverity.values)
    statuses = [IncidentStatus.RESOLVED, IncidentStatus.OPEN, IncidentStatus.INVESTIGATING, IncidentStatus.MONITORING, IncidentStatus.DISMISSED]

    for i in range(24):
        event = ctx.events[i % len(ctx.events)]
        org = event.organization
        payment = next((p for p in ctx.payments if p.order.event_id == event.id), None) if i % 4 == 0 else None
        scan_log = event.scan_logs.first() if i % 5 == 0 else None
        status = statuses[i % len(statuses)]
        severity = severities[i % len(severities)]
        category = categories[i % len(categories)]
        detected = min(ctx.as_of - timedelta(days=i*7+1), event.end_at if event.end_at < ctx.as_of else ctx.as_of - timedelta(days=i+1))
        resolution = ""
        if status == IncidentStatus.RESOLVED:
            resolution = choose([
                "Le traitement a été relancé et les contrôles de cohérence sont revenus au vert.",
                "L'équipe événement a corrigé la configuration et confirmé le retour nominal.",
                "Le paiement a été vérifié puis rapproché avec la commande correspondante.",
                "L'incident a été reproduit, corrigé et surveillé pendant deux cycles.",
            ], i)
        incident = upsert(OperationsIncident, f"incident-{i}", defaults={
            "title": choose([
                "Retard de traitement des notifications", "Pic de refus à une porte d'accès",
                "Paiement sandbox resté en traitement", "Stock billet proche de la saturation",
                "Worker Autopilot temporairement dégradé", "Demande support organisateur",
                "Vérification d'une activité de connexion inhabituelle", "Écart de configuration sur un événement",
            ], i),
            "category": category, "severity": severity, "status": status,
            "organization": org, "event": event, "payment": payment, "scan_log": scan_log,
            "description": "Incident historique de démonstration documenté avec contexte, propriétaire, chronologie et résultat pour simuler l'exploitation réelle de Makolo.",
            "resolution": resolution, "opened_by": staff[i % len(staff)], "assigned_to": staff[(i + 1) % len(staff)],
            "detected_at": detected, "acknowledged_at": detected + timedelta(minutes=12),
            "resolved_at": detected + timedelta(hours=2+i%5) if status == IncidentStatus.RESOLVED else None,
            "metadata": {"seed": "makolo-demo", "source": choose(["monitoring", "support", "finance", "access"], i)},
        })
        backdate(incident, created_at=detected, updated_at=incident.resolved_at or min(ctx.as_of, detected + timedelta(days=1)))
        audit = upsert(OperationsAuditLog, f"incident-{i}-audit", defaults={
            "actor": incident.assigned_to,
            "action": "incident.resolved" if status == IncidentStatus.RESOLVED else "incident.updated",
            "target_type": "operations_incident", "target_id": str(incident.id),
            "summary": f"Mise à jour Operations : {incident.title}",
            "before": {"status": IncidentStatus.OPEN}, "after": {"status": status},
            "metadata": {"seed": "makolo-demo", "severity": severity},
        })
        backdate(audit, created_at=incident.updated_at)

    for i in range(12):
        event = ctx.events[(i * 3) % len(ctx.events)]
        target = ModerationTarget.EVENT if i % 2 else ModerationTarget.ORGANIZATION
        status = choose([ModerationStatus.OPEN, ModerationStatus.REVIEWING, ModerationStatus.ACTIONED, ModerationStatus.DISMISSED], i)
        case = upsert(ModerationCase, f"moderation-{i}", defaults={
            "target_type": target, "organization": event.organization,
            "event": event if target == ModerationTarget.EVENT else None,
            "severity": choose(list(IncidentSeverity.values), i+1), "status": status,
            "reason": choose([
                "Vérification manuelle du contenu public avant mise en avant.",
                "Signalement de démonstration relatif aux informations de l'événement.",
                "Contrôle de conformité du profil organisateur.", "Revue d'un changement important sur la billetterie.",
            ], i),
            "outcome": "Revue terminée, aucun blocage persistant." if status in {ModerationStatus.ACTIONED, ModerationStatus.DISMISSED} else "",
            "opened_by": staff[i % len(staff)], "assigned_to": staff[(i+1) % len(staff)],
            "closed_at": ctx.as_of - timedelta(days=5+i) if status in {ModerationStatus.ACTIONED, ModerationStatus.DISMISSED} else None,
        })
        created = ctx.as_of - timedelta(days=70+i*8)
        backdate(case, created_at=created, updated_at=case.closed_at or ctx.as_of - timedelta(days=i+1))
        audit = upsert(OperationsAuditLog, f"moderation-{i}-audit", defaults={
            "actor": case.assigned_to, "action": "moderation.review", "target_type": "moderation_case",
            "target_id": str(case.id), "summary": "Dossier de modération révisé.",
            "before": {"status": ModerationStatus.OPEN}, "after": {"status": status}, "metadata": {"seed": "makolo-demo"},
        })
        backdate(audit, created_at=case.updated_at)

    for i, (name, instance, state, error) in enumerate([
        ("autopilot", "pythonanywhere-demo-1", WorkerState.HEALTHY, ""),
        ("notifications", "pythonanywhere-demo-1", WorkerState.DEGRADED, "Dernier cycle lent, surveillance en cours."),
        ("crm-delivery", "pythonanywhere-demo-1", WorkerState.STOPPED, "Worker volontairement arrêté dans le scénario de démonstration."),
    ]):
        heartbeat = upsert(WorkerHeartbeat, f"worker-{name}", defaults={
            "worker_name": name, "instance_id": instance, "state": state,
            "last_seen_at": ctx.as_of - timedelta(minutes=2 if state == WorkerState.HEALTHY else (18 if state == WorkerState.DEGRADED else 240)),
            "last_cycle_started_at": ctx.as_of - timedelta(minutes=4+i*10),
            "last_cycle_finished_at": ctx.as_of - timedelta(minutes=3+i*10) if state != WorkerState.STOPPED else ctx.as_of - timedelta(hours=5),
            "last_error": error, "metadata": {"seed": "makolo-demo", "host": "demo"},
        })
        backdate(heartbeat, created_at=ctx.as_of - timedelta(days=120-i*10), updated_at=heartbeat.last_seen_at)
