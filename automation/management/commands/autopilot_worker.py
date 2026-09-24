import json
import socket
import signal
import time

from django.core.management.base import BaseCommand

from automation.scheduler import run_autopilot_cycle
from core.logging_filters import redact_sensitive_text
from operations.emergency_controls import is_operational_control_enabled
from operations.models import OperationalControlCode, WorkerState
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
                safe_error = redact_sensitive_text(str(exc))
                self.stderr.write(
                    self.style.WARNING(
                        f"Heartbeat Operations indisponible: {safe_error}"
                    )
                )

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
                if not is_operational_control_enabled(OperationalControlCode.AUTOPILOT):
                    stats = {"operational_control": "disabled"}
                else:
                    stats = run_autopilot_cycle(delivery_limit=delivery_limit)
            except Exception as exc:
                safe_error = redact_sensitive_text(str(exc))
                heartbeat(
                    state=WorkerState.DEGRADED,
                    last_error=safe_error,
                    cycle_finished=True,
                    metadata={
                        "poll_seconds": poll_seconds,
                        "delivery_limit": delivery_limit,
                    },
                )
                self.stderr.write(
                    self.style.ERROR(f"Cycle Autopilot en échec: {safe_error}")
                )
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
