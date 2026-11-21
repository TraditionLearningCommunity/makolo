"""PostgreSQL regression: team quota admits only one net-new Profile under a race."""
from __future__ import annotations

import threading
import unittest
from importlib import import_module

from django.apps import apps

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import close_old_connections, connection, connections
from django.test import TransactionTestCase

from authorization.constants import SystemRoleCode
from organizations.models import TeamMembership, TeamMembershipStatus
from organizations.services import add_or_update_member, create_organization

from .models import FeatureDefinition
from .runtime_services import create_entitlement_grant

User = get_user_model()


@unittest.skipUnless(connection.vendor == "postgresql", "Team quota race requires PostgreSQL")
class TeamMemberQuotaConcurrencyTests(TransactionTestCase):
    def setUp(self):
        super().setUp()
        # TransactionTestCase flushes the database. Replaying the serialized
        # initial state here duplicates Django ContentType rows because
        # post_migrate already recreated them. Restore only the canonical
        # migration-seeded business catalog needed by this concurrency test.
        # No permission, quota, or race assertion is bypassed.
        import_module(
            "authorization.migrations.0002_seed_roles_and_backfill"
        ).seed_and_backfill(apps, None)
        import_module(
            "subscriptions.migrations.0002_seed_feature_definitions"
        ).seed_features(apps, None)

    def test_two_simultaneous_admissions_consume_one_last_slot(self):
        owner = User.objects.create_user(
            username="lot5-owner", email="lot5-owner@example.test", password="test-only",
        )
        space = create_organization(creator=owner, name="Lot5 Quota Race Space")
        candidates = [
            User.objects.create_user(username=f"lot5-candidate-{i}", password="test-only")
            for i in range(2)
        ]
        # One active owner already occupies a slot. Two different Profiles
        # contend for exactly one additional configured slot.
        create_entitlement_grant(
            space=space,
            feature=FeatureDefinition.objects.get(code="team.members"),
            value=2,
            reason="Lot 5 concurrency contract",
        )

        gate = threading.Barrier(2)
        outcomes = []
        exceptions = []
        result_lock = threading.Lock()

        def admit(profile_id):
            close_old_connections()
            try:
                gate.wait(timeout=10)
                try:
                    add_or_update_member(
                        organization=space,
                        actor=User.objects.get(pk=owner.pk),
                        user=User.objects.get(pk=profile_id),
                        role=SystemRoleCode.SPACE_ADMIN,
                    )
                    result = "admitted"
                except ValidationError as exc:
                    if "subscription" not in getattr(exc, "message_dict", {}):
                        raise
                    result = "limited"
                with result_lock:
                    outcomes.append(result)
            except Exception as exc:
                with result_lock:
                    exceptions.append(exc)
            finally:
                connections.close_all()

        workers = [
            threading.Thread(target=admit, args=(profile.pk,))
            for profile in candidates
        ]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join(timeout=20)

        self.assertFalse(any(worker.is_alive() for worker in workers))
        self.assertEqual(exceptions, [])
        self.assertCountEqual(outcomes, ["admitted", "limited"])
        active_ids = set(
            TeamMembership.objects.filter(
                team__organization=space,
                team__is_active=True,
                status=TeamMembershipStatus.ACTIVE,
            ).values_list("user_id", flat=True)
        )
        self.assertEqual(len(active_ids), 2)
        self.assertIn(owner.pk, active_ids)
        self.assertEqual(len(active_ids.intersection({c.pk for c in candidates})), 1)
