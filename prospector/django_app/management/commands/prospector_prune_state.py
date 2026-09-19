from __future__ import annotations

import json
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError

from prospector.django_operations import DjangoProspectorMaintenance


def _parse_aware(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise CommandError("--before must be an ISO-8601 datetime") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise CommandError("--before must include a timezone offset")
    return parsed


class Command(BaseCommand):
    help = (
        "Dry-run or prune only expired Prospector budget counters/reservations. "
        "Frontier, provenance, checkpoints and feedback events are never deleted."
    )

    def add_arguments(self, parser):
        parser.add_argument("--before", required=True)
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **options):
        result = DjangoProspectorMaintenance().prune_expired_budgets_sync(
            before=_parse_aware(options["before"]),
            apply=options["apply"],
        )
        self.stdout.write(
            json.dumps(
                {"kind": "prospector_prune_state", **result},
                ensure_ascii=False,
                allow_nan=False,
                sort_keys=True,
            )
        )
