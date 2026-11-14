"""Read-only schema preflight for existing demo databases."""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from scripts.demo_generation.schema import (
    DemoSchemaNotReady, assert_demo_schema_ready,
)


class DemoSchemaPreflightTests(SimpleTestCase):
    def _mock_connection(self, columns):
        fake = MagicMock()
        fake.cursor.return_value.__enter__.return_value = MagicMock()
        fake.introspection.get_table_description.return_value = [
            SimpleNamespace(name=name) for name in columns
        ]
        return fake

    @patch("scripts.demo_generation.schema.MigrationExecutor")
    def test_pending_migrations_fail_before_introspection(self, executor):
        migration = SimpleNamespace(
            app_label="journeys", name="0099_beneficiary_space"
        )
        executor.return_value.loader.graph.leaf_nodes.return_value = [
            ("journeys", "0099_beneficiary_space")
        ]
        executor.return_value.migration_plan.return_value = [
            (migration, False)
        ]
        with patch("scripts.demo_generation.schema.connection") as db:
            with self.assertRaisesRegex(
                DemoSchemaNotReady, "Base de demonstration non migree"
            ):
                assert_demo_schema_ready()
            db.cursor.assert_not_called()

    @patch("scripts.demo_generation.schema.MigrationExecutor")
    def test_missing_beneficiary_space_column_is_reported(self, executor):
        executor.return_value.migration_plan.return_value = []
        db = self._mock_connection(["id", "beneficiary_id"])
        with patch("scripts.demo_generation.schema.connection", db):
            with self.assertRaisesRegex(
                DemoSchemaNotReady, "beneficiary_space_id manque"
            ):
                assert_demo_schema_ready()

    @patch("scripts.demo_generation.schema.MigrationExecutor")
    def test_ready_schema_returns_without_writing(self, executor):
        executor.return_value.migration_plan.return_value = []
        db = self._mock_connection([
            "id", "beneficiary_id", "beneficiary_space_id",
        ])
        with patch("scripts.demo_generation.schema.connection", db):
            assert_demo_schema_ready()
            db.cursor.assert_called_once()
            db.introspection.get_table_description.assert_called_once()
            db.cursor.return_value.execute.assert_not_called()
