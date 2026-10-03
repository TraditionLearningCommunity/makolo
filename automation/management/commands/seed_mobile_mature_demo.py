from __future__ import annotations

import os
from datetime import datetime
from zoneinfo import ZoneInfo

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from demo_seed.common import SeedContext
from demo_seed.mobile_mature_universe import (
    MOBILE_MATURE_PERSONAS,
    seed_mobile_mature_universe,
)
from demo_seed.mobile_mature_validation import assert_mobile_mature_demo_coverage


TZ = ZoneInfo("Africa/Lubumbashi")


class Command(BaseCommand):
    help = "Seed only the self-contained Mobile Mature demo universe for Web/Flutter testing."

    def add_arguments(self, parser):
        parser.add_argument(
            "--as-of",
            required=True,
            help="Reference date in Africa/Lubumbashi (YYYY-MM-DD).",
        )
        parser.add_argument("--demo-password", default=None)

    def handle(self, *args, **options):
        password = options["demo_password"] or os.environ.get("MAKOLO_DEMO_PASSWORD")
        if not password:
            raise CommandError("Set MAKOLO_DEMO_PASSWORD or pass --demo-password.")

        try:
            as_of = datetime.strptime(options["as_of"], "%Y-%m-%d").replace(
                hour=0,
                minute=0,
                second=0,
                microsecond=0,
                tzinfo=TZ,
            )
        except ValueError as exc:
            raise CommandError("--as-of doit utiliser le format YYYY-MM-DD.") from exc

        ctx = SeedContext(
            as_of=as_of,
            scale="beta",
            demo_password=password,
        )

        with transaction.atomic():
            seed_mobile_mature_universe(ctx)
            validation = assert_mobile_mature_demo_coverage()

        self.stdout.write(self.style.SUCCESS("Mobile mature demo seed complete"))
        self.stdout.write(f"As of: {as_of.date().isoformat()}")
        for label, amount in sorted(validation.items()):
            self.stdout.write(f"{label}: {amount}")
        self.stdout.write("Login:")
        self.stdout.write(f"  {MOBILE_MATURE_PERSONAS['primary']}")
        self.stdout.write("Password source accepted; value intentionally not printed.")
