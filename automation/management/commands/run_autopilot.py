import json
import socket

from django.core.management.base import BaseCommand

from automation.crm_runtime import process_due_crm_workflows
from automation.services import run_autopilot_cycle
from capacity.services import expire_stale_capacity_reservations
from core.logging_filters import redact_sensitive_text
from domain_events.services import process_domain_events, recover_stale_domain_events
from journeys.services import expire_due_journeys
from operations.models import WorkerState
from operations.services import record_worker_heartbeat


class Command(BaseCommand):
    help = "Exécute un cycle Makolo Autopilot (scheduler, expirations, Domain Events, notifications et CRM)."

    def add_arguments(self, parser):
        parser.add_argument("--delivery-limit", type=int, default=100)
        parser.add_argument(
            "--record-scheduled-heartbeat",
            action="store_true",
            help=(
                "Enregistre ce cycle comme tâche planifiée horaire dans Operations. "
                "À utiliser pour un scheduler, pas pour un lancement manuel ponctuel."
            ),
        )
        parser.add_argument(
            "--instance-id",
            default=socket.gethostname(),
            help="Identifiant de l'instance scheduler dans Operations.",
        )

    def handle(self, *args, **options):
        limit = max(options["delivery_limit"], 1)
        record_scheduled = bool(options["record_scheduled_heartbeat"])
        instance_id = options["instance_id"] or socket.gethostname()
        metadata = {
            "mode": "scheduled",
            "expected_interval_seconds": 3600,
            "delivery_limit": limit,
        }
        if record_scheduled:
            record_worker_heartbeat(
                worker_name="autopilot",
                instance_id=instance_id,
                state=WorkerState.HEALTHY,
                metadata=metadata,
                cycle_started=True,
            )
        try:
            # Time-driven work remains scheduler-owned. Each canonical service
            # emits its own facts; the scheduler never duplicates workflow logic.
            canonical_stats = {
                "expired_capacity_holds": expire_stale_capacity_reservations(),
                "expired_journeys": expire_due_journeys(),
                "recovered_domain_events": recover_stale_domain_events(),
                "domain_events": process_domain_events(batch_size=limit, limit=limit),
            }
            stats = run_autopilot_cycle(delivery_limit=limit)
            stats.update(canonical_stats)
            stats["crm_workflows"] = process_due_crm_workflows(limit=limit)
        except Exception as exc:
            if record_scheduled:
                record_worker_heartbeat(
                    worker_name="autopilot",
                    instance_id=instance_id,
                    state=WorkerState.DEGRADED,
                    last_error=redact_sensitive_text(str(exc)),
                    metadata=metadata,
                    cycle_finished=True,
                )
            raise
        if record_scheduled:
            # A one-shot scheduler is expected to stop after a healthy cycle;
            # STOPPED avoids treating the absence of a persistent worker as an incident.
            record_worker_heartbeat(
                worker_name="autopilot",
                instance_id=instance_id,
                state=WorkerState.STOPPED,
                metadata={**metadata, "last_stats": stats},
                cycle_finished=True,
            )
        self.stdout.write(self.style.SUCCESS(json.dumps(stats, ensure_ascii=False, default=str)))
