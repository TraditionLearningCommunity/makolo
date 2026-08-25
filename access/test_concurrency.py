from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from unittest import skipUnless

from django.contrib.auth import get_user_model
from django.db import close_old_connections, connection
from django.test import TransactionTestCase
from django.utils import timezone

from activities.models import Activity, Occurrence

from .models import AccessUseResult, CredentialStatus
from .services import issue_access, render_access_credential, validate_access_credential


User = get_user_model()


@skipUnless(connection.vendor == "postgresql", "Ce test exerce le verrouillage PostgreSQL réel.")
class AccessConcurrencyTests(TransactionTestCase):
    reset_sequences = False

    def setUp(self):
        self.user = User.objects.create_user(
            username="access-concurrency",
            email="access-concurrency@example.com",
            password="Access-2026!",
        )
        self.activity = Activity.objects.create(
            owner_profile=self.user,
            created_by=self.user,
            title="Concurrent Access",
        )
        self.occurrence = Occurrence.objects.create(
            activity=self.activity,
            start_at=timezone.now() - timedelta(minutes=5),
            end_at=timezone.now() + timedelta(hours=1),
        )
        access = issue_access(
            beneficiary=self.user,
            activity=self.activity,
            occurrence=self.occurrence,
            single_use=True,
        )
        credential = access.credentials.get(status=CredentialStatus.ACTIVE)
        self.token = render_access_credential(credential)

    def _validate(self, barrier):
        close_old_connections()
        try:
            barrier.wait(timeout=5)
            outcome = validate_access_credential(
                self.token,
                expected_activity=self.activity,
                expected_occurrence=self.occurrence,
                source="postgres-concurrency-test",
            )
            return outcome.result
        finally:
            # The connection proxy is thread-local here. Close it explicitly so
            # PostgreSQL can drop Django's temporary test database at teardown.
            connection.close()

    def test_two_simultaneous_validations_accept_exactly_once(self):
        barrier = Barrier(2)
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(self._validate, barrier) for _ in range(2)]
            results = [future.result(timeout=10) for future in futures]

        self.assertEqual(results.count(AccessUseResult.ACCEPTED), 1)
        self.assertEqual(results.count(AccessUseResult.ALREADY_USED), 1)
