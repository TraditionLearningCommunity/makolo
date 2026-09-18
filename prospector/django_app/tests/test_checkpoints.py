from datetime import datetime, timezone

from django.test import TestCase

from prospector.django_checkpoints import DjangoSourceCheckpointStore
from prospector.source_contracts import SourceCheckpoint


class DjangoSourceCheckpointStoreTests(TestCase):
    def setUp(self):
        self.store = DjangoSourceCheckpointStore()
        self.now = datetime(2026, 9, 18, tzinfo=timezone.utc)

    def test_save_and_load_exact_mission_fingerprint(self):
        checkpoint = SourceCheckpoint(
            source_name="common_crawl_cdxj",
            mission_key="rdc",
            mission_fingerprint="a" * 64,
            source_revision="CC-MAIN-2026-34",
            cursor={"page": 2},
            exhausted=False,
            updated_at=self.now,
        )
        self.store.save_sync(checkpoint)
        loaded = self.store.load_sync(
            source_name="common_crawl_cdxj",
            mission_key="rdc",
            mission_fingerprint="a" * 64,
        )
        self.assertEqual(loaded.source_revision, "CC-MAIN-2026-34")
        self.assertEqual(loaded.cursor["page"], 2)

    def test_changed_mission_fingerprint_starts_without_old_cursor(self):
        checkpoint = SourceCheckpoint(
            source_name="common_crawl_cdxj",
            mission_key="rdc",
            mission_fingerprint="a" * 64,
            source_revision="CC-MAIN-2026-34",
            cursor={"page": 9},
            exhausted=True,
            updated_at=self.now,
        )
        self.store.save_sync(checkpoint)
        loaded = self.store.load_sync(
            source_name="common_crawl_cdxj",
            mission_key="rdc",
            mission_fingerprint="b" * 64,
        )
        self.assertIsNone(loaded)
