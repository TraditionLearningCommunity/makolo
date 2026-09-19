import io
import json
from datetime import datetime, timedelta, timezone
from unittest import skipUnless

from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test import TestCase, TransactionTestCase

from prospector.contracts import ProspectingCandidate, ProspectingEvidence
from prospector.django_app.models import ProspectorFrontierEntry
from prospector.django_frontier import DjangoFrontierStore
from prospector.frontier import FrontierState


POSTGRESQL = connection.vendor == "postgresql"


class OperationsCommandTests(TestCase):
    def setUp(self):
        self.now = datetime(2026, 9, 19, 12, 0, tzinfo=timezone.utc)

    def test_healthcheck_outputs_aggregate_json(self):
        stdout = io.StringIO()
        call_command(
            "prospector_healthcheck",
            "--max-stale-claims",
            "0",
            stdout=stdout,
        )
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["kind"], "prospector_health")
        self.assertEqual(payload["health"]["status"], "ok")

    def test_fail_on_degraded_returns_command_error(self):
        target = DjangoFrontierStore().admit_sync(
            ProspectingCandidate(
                locator="https://example.test/stale",
                kind="web_url",
                evidence=(
                    ProspectingEvidence(
                        method="external_index",
                        discovered_at=self.now,
                    ),
                ),
                available_at=self.now,
            )
        )
        ProspectorFrontierEntry.objects.filter(
            target_key=target.target_key
        ).update(
            status=FrontierState.CLAIMED.value,
            claimed_by="dead",
            claimed_at=self.now - timedelta(hours=1),
            lease_expires_at=self.now - timedelta(minutes=1),
            claim_token="22222222-2222-2222-2222-222222222222",
        )
        with self.assertRaises(CommandError):
            call_command(
                "prospector_healthcheck",
                "--max-stale-claims",
                "0",
                "--fail-on-degraded",
                stdout=io.StringIO(),
            )

    def test_rebuild_feedback_requires_all_explicit_weights(self):
        with self.assertRaises(CommandError):
            call_command(
                "prospector_rebuild_feedback",
                "--policy-key",
                "broken",
                "--weight",
                "reality_new=1",
                "--batch-size",
                "10",
                stdout=io.StringIO(),
            )


@skipUnless(POSTGRESQL, "query plan inspection requires PostgreSQL")
class PostgreSQLPlanCommandTests(TransactionTestCase):
    def test_frontier_plan_is_read_only_json(self):
        stdout = io.StringIO()
        call_command(
            "prospector_frontier_plan",
            "--limit",
            "20",
            stdout=stdout,
        )
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["kind"], "prospector_frontier_plan")
        self.assertEqual(payload["database"], "postgresql")
        self.assertEqual(payload["limit"], 20)
        self.assertIn("total_cost", payload)
