import io
import json
from datetime import datetime, timezone
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from prospector.providers.common_crawl import CommonCrawlIndexSource
from prospector.source_contracts import IndexedResource, SourceBatch


class FakeLiveCommonCrawl:
    name = "common_crawl_cdxj"

    async def discover(self, mission, *, checkpoint=None):
        return SourceBatch(
            source_name=self.name,
            source_revision="CC-MAIN-live-test",
            records=(
                IndexedResource(
                    provider="common_crawl",
                    locator="https://uni.cd/formation/network",
                    observed_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
                    source_revision="CC-MAIN-live-test",
                    source_ref="live:1",
                    status_code=200,
                    mime_type="text/html",
                ),
            ),
            next_cursor={"selector_index": 0, "page": 1, "offset": 0},
            exhausted=True,
        )


class ProspectorLivePilotCommandTests(TestCase):
    def args(self):
        return [
            "--user-agent",
            "Makolo PX8 test operator",
            "--mission-key",
            "px8-command-test",
            "--host-tld",
            "cd",
            "--path-term",
            "formation",
            "--max-candidates",
            "5",
            "--max-source-requests",
            "1",
            "--source-passes",
            "1",
            "--request-interval-seconds",
            "1",
            "--timeout-seconds",
            "5",
        ]

    def test_refuses_network_without_explicit_confirmation(self):
        with self.assertRaises(CommandError):
            call_command("prospector_live_pilot", *self.args())

    def test_confirmed_command_emits_aggregate_scorecard_without_network(self):
        stdout = io.StringIO()
        with patch(
            "prospector.django_app.management.commands.prospector_live_pilot.CommonCrawlIndexSource",
            return_value=FakeLiveCommonCrawl(),
        ):
            call_command(
                "prospector_live_pilot",
                "--confirm-live-internet",
                *self.args(),
                stdout=stdout,
            )
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["kind"], "prospector_px8_pilot")
        self.assertEqual(payload["source"]["received"], 1)
        self.assertEqual(payload["frontier"]["new_entries"], 1)
        self.assertIn(
            "observer_runtime_not_run",
            payload["limitations"],
        )
        rendered = stdout.getvalue()
        self.assertNotIn("https://uni.cd/formation/network", rendered)
