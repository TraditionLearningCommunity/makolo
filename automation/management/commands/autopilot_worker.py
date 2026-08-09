import json
import socket
import signal
import time

from django.core.management.base import BaseCommand

from automation.crm_runtime import process_due_crm_workflows
from automation.services import run_autopilot_cycle
from operations.models import WorkerState
from operations.services import record_worker_heartbeat


class Command(BaseCommand):
    help = "Lance le worker autonome Makolo Autopilot en boucle."

    def add_arguments(self, parser):
        parser.add_argument("--poll-seconds", type=int, default=30)
        parser.add_argument("--delivery-limit", type=int, default=100)

    def handle(self, *args, **options):
        poll_seconds = max(options["poll_seconds"], 5)
        delivery_limit = max(options["delivery_limit"], 1)
        running = True
        instance_id = socket.gethostname() or "default"

        def heartbeat(**kwargs):
            try:
                record_worker_heartbeat(
                    worker_name="autopilot",
                    instance_id=instance_id,
                    **kwargs,
                )
            except Exception as exc:
                self.stderr.write(self.style.WARNING(f"Heartbeat Operations indisponible: {exc}"))

        def stop(*_args):
            nonlocal running
            running = False

        signal.signal(signal.SIGTERM, stop)
        signal.signal(signal.SIGINT, stop)
        heartbeat(
            state=WorkerState.HEALTHY,
            metadata={"poll_seconds": poll_seconds, "delivery_limit": delivery_limit},
        )
        self.stdout.write(self.style.SUCCESS(f"Makolo Autopilot démarré (cycle toutes les {poll_seconds}s)."))
        while running:
            started = time.monotonic()
            heartbeat(
                state=WorkerState.HEALTHY,
                cycle_started=True,
                metadata={"poll_seconds": poll_seconds, "delivery_limit": delivery_limit},
            )
            try:
                stats = run_autopilot_cycle(delivery_limit=delivery_limit)
                stats["crm_workflows"] = process_due_crm_workflows(limit=delivery_limit)
            except Exception as exc:
                heartbeat(
                    state=WorkerState.DEGRADED,
                    last_error=str(exc),
                    cycle_finished=True,
                    metadata={"poll_seconds": poll_seconds, "delivery_limit": delivery_limit},
                )
                self.stderr.write(self.style.ERROR(f"Cycle Autopilot en échec: {exc}"))
            else:
                heartbeat(
                    state=WorkerState.HEALTHY,
                    last_error="",
                    cycle_finished=True,
                    metadata={"poll_seconds": poll_seconds, "delivery_limit": delivery_limit, "last_stats": stats},
                )
                self.stdout.write(json.dumps(stats, ensure_ascii=False, default=str))
            elapsed = time.monotonic() - started
            remaining = max(poll_seconds - elapsed, 1)
            if running:
                time.sleep(remaining)
        heartbeat(state=WorkerState.STOPPED, last_error="", cycle_finished=True)
        self.stdout.write(self.style.SUCCESS("Makolo Autopilot arrêté proprement."))
