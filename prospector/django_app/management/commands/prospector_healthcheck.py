from __future__ import annotations

import json

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from prospector.django_operations import DjangoOperationsReader
from prospector.operations import (
    OperationsThresholds,
    evaluate_operations_health,
)


class Command(BaseCommand):
    help = "Emit aggregate Prospector operational health without locators or content."

    def add_arguments(self, parser):
        parser.add_argument("--max-stale-claims", type=int)
        parser.add_argument("--max-ready-age-seconds", type=int)
        parser.add_argument("--max-feedback-lag-events", type=int)
        parser.add_argument("--max-checkpoint-age-seconds", type=int)
        parser.add_argument("--fail-on-degraded", action="store_true")

    def handle(self, *args, **options):
        thresholds = OperationsThresholds(
            max_stale_claims=options["max_stale_claims"],
            max_ready_age_seconds=options["max_ready_age_seconds"],
            max_feedback_projection_lag_events=options["max_feedback_lag_events"],
            max_active_checkpoint_age_seconds=options["max_checkpoint_age_seconds"],
        )
        snapshot = DjangoOperationsReader().snapshot_sync(now=timezone.now())
        health = evaluate_operations_health(snapshot, thresholds)
        payload = {
            "kind": "prospector_health",
            "health": health.to_dict(),
            "snapshot": snapshot.to_dict(),
        }
        self.stdout.write(
            json.dumps(
                payload,
                ensure_ascii=False,
                allow_nan=False,
                sort_keys=True,
            )
        )
        if options["fail_on_degraded"] and health.status != "ok":
            raise CommandError(
                "Prospector operational health is degraded; see JSON output."
            )
