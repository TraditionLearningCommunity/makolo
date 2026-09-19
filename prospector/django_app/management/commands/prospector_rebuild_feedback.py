from __future__ import annotations

import json

from django.core.management.base import BaseCommand, CommandError

from prospector.django_feedback import DjangoFeedbackStore
from prospector.feedback import FeedbackPolicy, FeedbackSignal


def _weights(values) -> dict:
    parsed = {}
    for raw in values:
        if "=" not in raw:
            raise CommandError("--weight must use signal=integer")
        name, raw_value = raw.split("=", 1)
        name = name.strip()
        try:
            signal = FeedbackSignal(name)
        except ValueError as exc:
            raise CommandError(f"unknown feedback signal {name!r}") from exc
        try:
            value = int(raw_value)
        except ValueError as exc:
            raise CommandError(f"weight for {name!r} must be an integer") from exc
        parsed[signal] = value
    return parsed


class Command(BaseCommand):
    help = (
        "Dry-run or rebuild one PX7 feedback projection from immutable raw events."
    )

    def add_arguments(self, parser):
        parser.add_argument("--policy-key", required=True)
        parser.add_argument(
            "--weight",
            action="append",
            default=[],
            help="Repeat for every signal: --weight reality_new=8",
        )
        parser.add_argument("--batch-size", type=int, required=True)
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **options):
        try:
            policy = FeedbackPolicy(
                policy_key=options["policy_key"],
                weights=_weights(options["weight"]),
            )
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        result = DjangoFeedbackStore().rebuild_projection_sync(
            policy,
            batch_size=options["batch_size"],
            apply=options["apply"],
        )
        self.stdout.write(
            json.dumps(
                {"kind": "prospector_rebuild_feedback", **result},
                ensure_ascii=False,
                allow_nan=False,
                sort_keys=True,
            )
        )
