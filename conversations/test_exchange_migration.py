"""Historical identities/replies survive the additive stream migration."""
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

from .test_exchange_stream import ExchangeFixture


class ExchangeMigrationTests(ExchangeFixture, TransactionTestCase):
    def test_old_rows_backfill_in_deterministic_order_without_recreating_them(self):
        first = self.send(reference="historical-first")
        second = self.send(reference="historical-second", reply_to=first)
        ids = (first.pk, second.pk)
        created = (first.created_at, second.created_at)
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        try:
            executor.migrate([("conversations", "0008_collective_access")])
            executor = MigrationExecutor(connection)
            executor.migrate(latest)
            from .point_models import ConversationPoint, PointExchangeEntry
            rows = list(PointExchangeEntry.objects.filter(point=self.point).order_by("sequence"))
            self.assertEqual(tuple(row.pk for row in rows), ids)
            self.assertEqual(tuple(row.created_at for row in rows), created)
            self.assertEqual([row.sequence for row in rows], [1, 2])
            self.assertEqual(rows[1].reply_to_id, first.pk)
            self.assertEqual(rows[0].body, "Message initial")
            self.assertEqual(ConversationPoint.objects.get(pk=self.point.pk).exchange_stream_version, 2)
            self.assertEqual(len(rows[0].origin_payload_hash), 64)
        finally:
            MigrationExecutor(connection).migrate(latest)
