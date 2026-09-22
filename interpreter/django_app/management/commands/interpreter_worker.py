from __future__ import annotations

import socket
import time

from django.core.management.base import BaseCommand

from interpreter.django_runtime import run_interpreter_cycle


class Command(BaseCommand):
    help = "Process finalized ObservationMaterial with Makolo Interpreter without refetching external sources."

    def add_arguments(self, parser):
        parser.add_argument("--instance-id", default=socket.gethostname())
        parser.add_argument("--batch-size", type=int, default=20)
        parser.add_argument("--lease-seconds", type=int, default=300)
        parser.add_argument("--poll-seconds", type=float, default=5.0)
        parser.add_argument("--observation-ref")
        parser.add_argument("--once", action="store_true")

    def handle(self, *args, **options):
        worker_id = (options["instance_id"] or "").strip()
        if not worker_id:
            self.stderr.write("empty instance-id")
            return
        while True:
            stats = run_interpreter_cycle(
                worker_id=worker_id,
                batch_size=max(int(options["batch_size"]), 1),
                lease_seconds=max(int(options["lease_seconds"]), 1),
                observation_ref=options.get("observation_ref"),
            )
            self.stdout.write("interpreter cycle " + " ".join(f"{key}={value}" for key, value in sorted(stats.items())))
            if options["once"]:
                return
            time.sleep(max(float(options["poll_seconds"]), 0.1))
