from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from unittest import skipUnless

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import close_old_connections, connection
from django.test import TransactionTestCase
from django.utils import timezone

from activities.models import Activity, ActivityStatus, Occurrence, OccurrenceStatus
from authorization.constants import PermissionCode
from authorization.models import AuthorityScope, Mandate, Permission, Role, RolePermission
from organizations.models import Organization

from .manual_grants import grant_access_manually
from .models import Access, AccessStatus


User = get_user_model()


@skipUnless(connection.vendor == "postgresql", "Ce test exerce le verrouillage PostgreSQL réel.")
class ManualAccessGrantConcurrencyTests(TransactionTestCase):
    reset_sequences = False

    def setUp(self):
        self.creator = User.objects.create_user(
            username="manual-concurrency-creator",
            email="manual-concurrency-creator@example.com",
        )
        self.actor = User.objects.create_user(
            username="manual-concurrency-actor",
            email="manual-concurrency-actor@example.com",
        )
        self.beneficiary = User.objects.create_user(
            username="manual-concurrency-beneficiary",
            email="manual-concurrency-beneficiary@example.com",
        )
        self.space = Organization.objects.create(
            name="Manual concurrency",
            created_by=self.creator,
        )
        self.activity = Activity.objects.create(
            space=self.space,
            created_by=self.creator,
            title="Concurrent manual grant",
            status=ActivityStatus.PUBLISHED,
        )
        self.occurrence = Occurrence.objects.create(
            activity=self.activity,
            start_at=timezone.now() + timedelta(days=2),
            end_at=timezone.now() + timedelta(days=2, hours=1),
            status=OccurrenceStatus.SCHEDULED,
        )

        permission, _ = Permission.objects.get_or_create(
            code=PermissionCode.ACTIVITY_ACCESS_MANAGE,
            defaults={
                "name": "Gérer les accès d’une activité",
                "description": "Permission canonique utilisée par le test concurrent.",
                "domain": "access",
                "scope_type": AuthorityScope.ACTIVITY,
                "is_system": True,
                "is_active": True,
            },
        )
        role = Role.objects.create(
            code="task18-concurrency-access-manager",
            name="Task 18 concurrency access manager",
            scope_type=AuthorityScope.ACTIVITY,
            is_system=True,
            is_active=True,
        )
        RolePermission.objects.create(role=role, permission=permission)
        Mandate.objects.create(
            profile=self.actor,
            role=role,
            scope_type=AuthorityScope.ACTIVITY,
            activity=self.activity,
        )

    def _grant(self, barrier):
        close_old_connections()
        try:
            barrier.wait(timeout=5)
            try:
                access = grant_access_manually(
                    actor=self.actor,
                    beneficiary=self.beneficiary,
                    activity=self.activity,
                    occurrence=self.occurrence,
                )
                return "created", str(access.pk)
            except ValidationError:
                return "duplicate", None
        finally:
            connection.close()

    def test_two_simultaneous_posts_create_one_active_access(self):
        barrier = Barrier(2)
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(self._grant, barrier) for _ in range(2)]
            results = [future.result(timeout=15) for future in futures]

        labels = [item[0] for item in results]
        self.assertEqual(labels.count("created"), 1)
        self.assertEqual(labels.count("duplicate"), 1)
        self.assertEqual(
            Access.objects.filter(
                beneficiary=self.beneficiary,
                activity=self.activity,
                occurrence=self.occurrence,
                status=AccessStatus.VALID,
            ).count(),
            1,
        )
