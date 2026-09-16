from __future__ import annotations

from datetime import date

from django.core.management.base import BaseCommand, CommandError

from activities.models import Occurrence
from opportunities.models import Opportunity, OpportunityKind

from .seed_makolo_world import counts


MINIMUMS = {
    "smoke": {
        "users": 8,
        "spaces": 4,
        "activities": 20,
        "occurrences": 40,
        "opportunities": 15,
        "journeys": 25,
        "conversations": 8,
        "contributions": 50,
        "total_records": 450,
    },
    "full": {
        "users": 100,
        "spaces": 30,
        "activities": 400,
        "occurrences": 800,
        "opportunities": 300,
        "journeys": 700,
        "conversations": 150,
        "contributions": 1400,
        "total_records": 10000,
    },
}


class Command(BaseCommand):
    help = "Validate the deterministic Makolo 2025-2026 synthetic demo world."

    def add_arguments(self, parser):
        parser.add_argument("--profile", choices=sorted(MINIMUMS), default="full")
        parser.add_argument("--as-of", required=True, help="Reference date YYYY-MM-DD.")

    def handle(self, *args, **options):
        profile = options["profile"]
        try:
            as_of = date.fromisoformat(options["as_of"])
        except ValueError as exc:
            raise CommandError("--as-of doit utiliser le format YYYY-MM-DD.") from exc

        observed = counts()
        failures = []
        for label, minimum in MINIMUMS[profile].items():
            value = observed.get(label, 0)
            if value < minimum:
                failures.append(f"{label}: {value} < {minimum}")

        world_occurrences = Occurrence.objects.filter(activity__slug__startswith="world-")
        historical_2025 = world_occurrences.filter(start_date__lt=date(2026, 1, 1)).count()
        future = world_occurrences.filter(start_date__gt=as_of).count()

        if profile == "full":
            if historical_2025 < 200:
                failures.append(f"historical_2025_occurrences: {historical_2025} < 200")
            if future < 50:
                failures.append(f"future_occurrences: {future} < 50")

            represented_kinds = set(
                Opportunity.objects.filter(
                    sources__external_reference__startswith="WORLD-"
                ).values_list("kind", flat=True)
            )
            missing = set(OpportunityKind.values) - represented_kinds
            if missing:
                failures.append("missing_opportunity_kinds: " + ", ".join(sorted(missing)))

        self.stdout.write("Makolo world dataset counts:")
        for label, value in sorted(observed.items()):
            self.stdout.write(f"  {label}: {value}")
        self.stdout.write(f"  historical_2025_occurrences: {historical_2025}")
        self.stdout.write(f"  future_occurrences_after_{as_of.isoformat()}: {future}")

        if failures:
            raise CommandError("Validation failed:\n- " + "\n- ".join(failures))

        self.stdout.write(self.style.SUCCESS("Makolo realistic synthetic world validation passed."))
