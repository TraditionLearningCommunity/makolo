from __future__ import annotations

import json
from pathlib import Path

from asgiref.sync import async_to_sync
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from prospector.django_checkpoints import DjangoSourceCheckpointStore
from prospector.django_frontier import DjangoFrontierStore
from prospector.django_pilot import DjangoPilotSnapshotReader
from prospector.pilot import (
    PilotPolicy,
    ProspectorPilotRunner,
    build_pilot_scorecard,
)
from prospector.providers.common_crawl import CommonCrawlIndexSource
from prospector.source_contracts import ProspectingMission
from prospector.source_runner import IndexProspector


class Command(BaseCommand):
    help = (
        "Run a bounded PX8 live Common Crawl prospecting pilot into the "
        "Prospector Frontier. This command does not invent or start an "
        "Observer deployment queue."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--confirm-live-internet",
            action="store_true",
            help="Required acknowledgement that this command will contact Common Crawl.",
        )
        parser.add_argument("--user-agent", required=True)
        parser.add_argument("--mission-key", required=True)
        parser.add_argument("--host-tld", action="append", required=True)
        parser.add_argument("--path-term", action="append", required=True)
        parser.add_argument("--language", action="append", default=[])
        parser.add_argument("--media-type", action="append", default=[])
        parser.add_argument("--max-candidates", type=int, required=True)
        parser.add_argument("--max-source-requests", type=int, required=True)
        parser.add_argument("--source-passes", type=int, required=True)
        parser.add_argument("--request-interval-seconds", type=float, required=True)
        parser.add_argument("--timeout-seconds", type=int, required=True)
        parser.add_argument("--report-file", default="")

    def handle(self, *args, **options):
        if not options["confirm_live_internet"]:
            raise CommandError(
                "Refusing live Internet access without --confirm-live-internet."
            )
        if options["request_interval_seconds"] <= 0:
            raise CommandError(
                "--request-interval-seconds must be > 0 for a live PX8 pilot."
            )
        if options["max_source_requests"] < 1:
            raise CommandError("--max-source-requests must be positive.")
        if options["source_passes"] < 1:
            raise CommandError("--source-passes must be positive.")
        if options["timeout_seconds"] < 1:
            raise CommandError("--timeout-seconds must be positive.")

        started_at = timezone.now()
        mission = ProspectingMission(
            mission_key=options["mission_key"],
            issued_at=started_at,
            host_tlds=tuple(options["host_tld"]),
            languages=tuple(options["language"]),
            path_terms=tuple(options["path_term"]),
            media_types=tuple(options["media_type"] or ("text/html",)),
            max_candidates=options["max_candidates"],
            context={
                "pilot": True,
                "pilot_kind": "px8_common_crawl_live",
            },
        )
        policy = PilotPolicy(
            max_source_passes=options["source_passes"],
            max_runtime_cycles=0,
        )
        snapshots = DjangoPilotSnapshotReader()
        before = snapshots.snapshot_sync(
            mission_key=mission.mission_key,
            mission_fingerprint=mission.fingerprint,
        )

        source = CommonCrawlIndexSource(
            user_agent=options["user_agent"],
            timeout_seconds=options["timeout_seconds"],
            max_requests_per_run=options["max_source_requests"],
            request_interval_seconds=options["request_interval_seconds"],
        )
        source_runner = IndexProspector(
            frontier=DjangoFrontierStore(),
            checkpoints=DjangoSourceCheckpointStore(),
        )
        runner = ProspectorPilotRunner(source_runner=source_runner)
        run = async_to_sync(runner.run)(
            source=source,
            mission=mission,
            policy=policy,
        )

        finished_at = timezone.now()
        after = snapshots.snapshot_sync(
            mission_key=mission.mission_key,
            mission_fingerprint=mission.fingerprint,
        )
        scorecard = build_pilot_scorecard(
            mission=mission,
            policy=policy,
            run=run,
            before=before,
            after=after,
            started_at=started_at,
            finished_at=finished_at,
        )
        rendered = json.dumps(
            scorecard,
            ensure_ascii=False,
            allow_nan=False,
            indent=2,
            sort_keys=True,
        )
        self.stdout.write(rendered)

        report_file = options["report_file"].strip()
        if report_file:
            path = Path(report_file)
            if path.exists() and path.is_dir():
                raise CommandError("--report-file must be a file path, not a directory.")
            if not path.parent.exists():
                raise CommandError(
                    f"report parent directory does not exist: {path.parent}"
                )
            path.write_text(rendered + "\n", encoding="utf-8")
            self.stderr.write(f"PX8 scorecard written to {path}")
