from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from demo_seed.beta_validation import BetaScenarioValidationError, assert_beta_scenario_coverage
from seed_makolo_demo import _parse_as_of


class Command(BaseCommand):
    help = "Read-only validation of the canonical Makolo beta scenarios."

    def add_arguments(self, parser):
        parser.add_argument("--as-of", required=True, help="Reference date used by the beta seed (YYYY-MM-DD).")

    def handle(self, *args, **options):
        try:
            as_of = _parse_as_of(options["as_of"])
            report = assert_beta_scenario_coverage(as_of=as_of)
        except (ValueError, BetaScenarioValidationError) as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(self.style.SUCCESS("Makolo beta scenarios: OK"))
        for label, amount in report.items():
            self.stdout.write(f"{label}: {amount}")
