from collections import Counter
from datetime import timedelta

from django.utils import timezone

from tickets.models import Ticket, TicketStatus

from .models import EventAccessGate, ScanLog, ScanResult


REJECTION_RESULTS = {
    ScanResult.DUPLICATE,
    ScanResult.INVALID_TOKEN,
    ScanResult.UNKNOWN_TICKET,
    ScanResult.WRONG_EVENT,
    ScanResult.INVALID_STATUS,
    ScanResult.EVENT_UNAVAILABLE,
    ScanResult.GATE_UNAVAILABLE,
}


def _rate(part, total):
    return round((part / total) * 100, 1) if total else 0.0


def _window(logs, *, now, minutes):
    rows = list(
        logs.filter(scanned_at__gte=now - timedelta(minutes=minutes)).values_list(
            "result", flat=True
        )
    )
    counts = Counter(rows)
    attempts = len(rows)
    accepted = counts[ScanResult.ACCEPTED]
    rejected = attempts - accepted
    return {
        "minutes": minutes,
        "attempts": attempts,
        "accepted": accepted,
        "rejected": rejected,
        "rejection_rate": _rate(rejected, attempts),
        "accepted_per_minute": round(accepted / minutes, 2),
        "duplicates": counts[ScanResult.DUPLICATE],
        "invalid_qr": counts[ScanResult.INVALID_TOKEN] + counts[ScanResult.UNKNOWN_TICKET],
        "wrong_event": counts[ScanResult.WRONG_EVENT],
        "gate_unavailable": counts[ScanResult.GATE_UNAVAILABLE],
    }


def _gate_metrics(gate, logs, *, now):
    gate_logs = logs.filter(access_gate=gate)
    last_15 = _window(gate_logs, now=now, minutes=15)
    last_60 = _window(gate_logs, now=now, minutes=60)
    target = max(gate.throughput_target_per_minute, 1)
    utilization = round((last_15["accepted_per_minute"] / target) * 100, 1)
    if not gate.is_active:
        state = "paused"
    elif utilization >= 100:
        state = "critical"
    elif utilization >= 75:
        state = "busy"
    elif last_15["attempts"] >= 5 and last_15["rejection_rate"] >= gate.warning_rejection_rate:
        state = "warning"
    else:
        state = "normal"
    return {
        "id": str(gate.pk),
        "name": gate.name,
        "slug": gate.slug,
        "is_active": gate.is_active,
        "throughput_target_per_minute": gate.throughput_target_per_minute,
        "warning_rejection_rate": gate.warning_rejection_rate,
        "utilization_percent": utilization,
        "state": state,
        "last_15": last_15,
        "last_60": last_60,
        "active_assignments": gate.assignments.filter(is_active=True).count(),
    }


def _velocity_series(logs, *, now):
    start = now - timedelta(minutes=60)
    rows = list(
        logs.filter(scanned_at__gte=start).values_list("scanned_at", "result")
    )
    points = []
    for index in range(12):
        bucket_start = start + timedelta(minutes=index * 5)
        bucket_end = bucket_start + timedelta(minutes=5)
        bucket = [result for scanned_at, result in rows if bucket_start <= scanned_at < bucket_end]
        accepted = sum(1 for result in bucket if result == ScanResult.ACCEPTED)
        points.append(
            {
                "at": bucket_start,
                "attempts": len(bucket),
                "accepted": accepted,
                "rejected": len(bucket) - accepted,
            }
        )
    return points


def _incidents(*, event_window, gates):
    incidents = []
    if event_window["attempts"] >= 5 and event_window["rejection_rate"] >= 30:
        incidents.append(
            {
                "kind": "high_rejection_rate",
                "severity": "high" if event_window["rejection_rate"] >= 50 else "medium",
                "title": "Taux de refus élevé",
                "detail": f"{event_window['rejection_rate']} % de refus sur les 15 dernières minutes.",
            }
        )
    if event_window["duplicates"] >= 3:
        incidents.append(
            {
                "kind": "duplicate_spike",
                "severity": "medium",
                "title": "Pic de doubles scans",
                "detail": f"{event_window['duplicates']} doubles scans sur les 15 dernières minutes.",
            }
        )
    if event_window["invalid_qr"] >= 3:
        incidents.append(
            {
                "kind": "invalid_qr_spike",
                "severity": "medium",
                "title": "Pic de QR invalides",
                "detail": f"{event_window['invalid_qr']} QR invalides ou inconnus récemment.",
            }
        )
    if event_window["wrong_event"] >= 2:
        incidents.append(
            {
                "kind": "wrong_event_spike",
                "severity": "medium",
                "title": "Billets d’un autre événement",
                "detail": f"{event_window['wrong_event']} tentative(s) avec un billet d’un autre événement.",
            }
        )

    for gate in gates:
        window = gate["last_15"]
        if gate["state"] == "critical":
            incidents.append(
                {
                    "kind": "gate_congestion",
                    "severity": "high",
                    "gate": gate["name"],
                    "title": f"Congestion probable · {gate['name']}",
                    "detail": (
                        f"Débit à {gate['utilization_percent']} % de la cible configurée "
                        "sur les 15 dernières minutes."
                    ),
                }
            )
        elif window["attempts"] >= 5 and window["rejection_rate"] >= gate["warning_rejection_rate"]:
            incidents.append(
                {
                    "kind": "gate_rejection_rate",
                    "severity": "medium",
                    "gate": gate["name"],
                    "title": f"Refus élevés · {gate['name']}",
                    "detail": f"{window['rejection_rate']} % de refus à cette porte.",
                }
            )
    return incidents


def event_access_snapshot(event):
    """Read-only operational snapshot for one event.

    No PII is returned. Metrics are computed from scanner/ticket source-of-truth
    rows and all rates use a bounded recent window so the dashboard can refresh
    frequently without creating another analytics table.
    """
    now = timezone.now()
    logs = ScanLog.objects.filter(event=event)
    gates_qs = EventAccessGate.objects.filter(event=event).prefetch_related("assignments")

    tickets = Ticket.objects.filter(event=event)
    issued = tickets.filter(status__in=[TicketStatus.VALID, TicketStatus.USED]).count()
    used = tickets.filter(status=TicketStatus.USED).count()

    last_5 = _window(logs, now=now, minutes=5)
    last_15 = _window(logs, now=now, minutes=15)
    last_60 = _window(logs, now=now, minutes=60)
    gate_rows = [_gate_metrics(gate, logs, now=now) for gate in gates_qs]

    unassigned_logs = logs.filter(access_gate__isnull=True)
    unassigned_15 = _window(unassigned_logs, now=now, minutes=15)
    if unassigned_15["attempts"]:
        gate_rows.append(
            {
                "id": None,
                "name": "Non attribué / terminaux hérités",
                "slug": "",
                "is_active": True,
                "throughput_target_per_minute": None,
                "warning_rejection_rate": 30,
                "utilization_percent": None,
                "state": "warning" if unassigned_15["rejection_rate"] >= 30 else "normal",
                "last_15": unassigned_15,
                "last_60": _window(unassigned_logs, now=now, minutes=60),
                "active_assignments": 0,
            }
        )

    incidents = _incidents(event_window=last_15, gates=gate_rows)
    recommendations = []
    if any(item["kind"] == "gate_congestion" for item in incidents):
        recommendations.append("Ouvrir une porte supplémentaire ou rediriger une partie du flux vers une porte moins chargée.")
    if any(item["kind"] == "duplicate_spike" for item in incidents):
        recommendations.append("Vérifier les tentatives de réutilisation et guider les agents sur le message « billet déjà utilisé ».")
    if any(item["kind"] == "invalid_qr_spike" for item in incidents):
        recommendations.append("Vérifier que les participants présentent bien le QR Makolo actuel et non une ancienne capture après transfert.")
    if last_15["attempts"] and last_15["rejection_rate"] >= 30:
        recommendations.append("Contrôler les motifs de refus dans le journal avant de modifier les règles d’accès.")
    if not recommendations:
        recommendations.append("Flux d’accès stable sur la fenêtre récente. Continuer la surveillance des portes actives.")

    return {
        "generated_at": now,
        "event": {
            "id": str(event.pk),
            "slug": event.slug,
            "title": event.title,
            "start_at": event.start_at,
            "end_at": event.end_at,
            "capacity": event.capacity,
        },
        "attendance": {
            "issued_or_used_tickets": issued,
            "checked_in": used,
            "remaining_not_checked_in": max(issued - used, 0),
            "check_in_rate": _rate(used, issued),
            "capacity_fill_rate": _rate(used, event.capacity) if event.capacity else None,
        },
        "windows": {"last_5": last_5, "last_15": last_15, "last_60": last_60},
        "gates": gate_rows,
        "velocity": _velocity_series(logs, now=now),
        "incidents": incidents,
        "recommendations": recommendations,
    }
