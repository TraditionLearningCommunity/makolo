import json
import signal
import time

from django.core.management.base import BaseCommand

from automation.crm_services import process_due_crm_workflows
from automation.services import run_autopilot_cycle


class Command(BaseCommand):
    help = "Lance le worker autonome Makolo Autopilot en boucle."

    def add_arguments(self, parser):
        parser.add_argument("--poll-seconds", type=int, default=30)
        parser.add_argument("--delivery-limit", type=int, default=100)

    def handle(self, *args, **options):
        poll_seconds = max(options["poll_seconds"], 5)
        delivery_limit = max(options["delivery_limit"], 1)
        running = True

        def stop(*_args):
            nonlocal running
            running = False

        signal.signal(signal.SIGTERM, stop)
        signal.signal(signal.SIGINT, stop)
        self.stdout.write(self.style.SUCCESS(f"Makolo Autopilot démarré (cycle toutes les {poll_seconds}s)."))
        while running:
            started = time.monotonic()
            try:
                stats = run_autopilot_cycle(delivery_limit=delivery_limit)
                stats["crm_workflows"] = process_due_crm_workflows(limit=delivery_limit)
            except Exception as exc:
                self.stderr.write(self.style.ERROR(f"Cycle Autopilot en échec: {exc}"))
            else:
                self.stdout.write(json.dumps(stats, ensure_ascii=False, default=str))
            elapsed = time.monotonic() - started
            remaining = max(poll_seconds - elapsed, 1)
            if running:
                time.sleep(remaining)
        self.stdout.write(self.style.SUCCESS("Makolo Autopilot arrêté proprement."))
