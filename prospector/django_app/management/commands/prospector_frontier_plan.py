from __future__ import annotations

import json

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from prospector.django_operations import DjangoProspectorMaintenance
from prospector.errors import ProspectorContractError


class Command(BaseCommand):
    help = (
        "Inspect PostgreSQL EXPLAIN metadata for the critical Frontier claim query. "
        "This command is read-only and has no latency pass/fail threshold."
    )

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, required=True)

    def handle(self, *args, **options):
        try:
            plan = DjangoProspectorMaintenance().frontier_claim_plan_sync(
                now=timezone.now(),
                limit=options["limit"],
            )
        except ProspectorContractError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(
            json.dumps(
                {"kind": "prospector_frontier_plan", **plan},
                ensure_ascii=False,
                allow_nan=False,
                sort_keys=True,
            )
        )
