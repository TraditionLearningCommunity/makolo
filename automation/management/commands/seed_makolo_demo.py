from __future__ import annotations

import os

from django.core.management.base import BaseCommand, CommandError

from demo_seed.common import SCALE
from seed_makolo_demo import run_seed


class Command(BaseCommand):
    help = "Seed deterministic Makolo demo data. The canonical beta profile requires an explicit reference date."

    def add_arguments(self, parser):
        parser.add_argument("--scale", choices=sorted(SCALE), default="beta")
        parser.add_argument("--as-of", required=True, help="Reference date in Africa/Lubumbashi (YYYY-MM-DD).")
        parser.add_argument("--demo-password", default=None)

    def handle(self, *args, **options):
        demo_password = options["demo_password"] or os.environ.get("MAKOLO_DEMO_PASSWORD")
        if not demo_password:
            raise CommandError("Set MAKOLO_DEMO_PASSWORD or pass --demo-password.")
        try:
            report = run_seed(
                scale=options["scale"],
                as_of=options["as_of"],
                demo_password=demo_password,
            )
        except ValueError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(self.style.SUCCESS("Makolo demo seed complete"))
        self.stdout.write(f"Scale: {report['scale']}")
        self.stdout.write(f"As of: {report['as_of']}")
        for label, amount in report["stats"].items():
            self.stdout.write(f"{label}: {amount}")
        if report["validation"]:
            self.stdout.write("Beta scenario validation:")
            for label, amount in report["validation"].items():
                self.stdout.write(f"  {label}: {amount}")
        self.stdout.write("Login examples:")
        for email in report["login_examples"]:
            self.stdout.write(f"  {email}")
        self.stdout.write("Password source accepted; value intentionally not printed.")
