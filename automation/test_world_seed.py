from django.core.management import call_command
from django.test import TestCase

from automation.management.commands.seed_makolo_world import counts


class RealisticWorldSeedTests(TestCase):
    def test_smoke_world_is_idempotent_and_valid(self):
        kwargs = {
            "profile": "smoke",
            "as_of": "2026-09-16",
            "demo_password": "TestOnly-World-Password!",
        }

        call_command("seed_makolo_world", **kwargs)
        first = counts()

        call_command("seed_makolo_world", **kwargs)
        second = counts()

        self.assertEqual(first, second)
        self.assertGreaterEqual(second["users"], 8)
        self.assertGreaterEqual(second["activities"], 20)
        self.assertGreaterEqual(second["opportunities"], 15)
        self.assertGreaterEqual(second["conversations"], 8)

        call_command(
            "validate_makolo_world",
            profile="smoke",
            as_of="2026-09-16",
        )
