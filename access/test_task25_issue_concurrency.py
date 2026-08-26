from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from unittest import skipUnless

from django.contrib.auth import get_user_model
from django.db import close_old_connections, connection
from django.test import TransactionTestCase
from django.utils import timezone

from activities.models import Activity, Occurrence
from journeys.beneficiary_services import create_external_beneficiary, create_journey_for_holder
from journeys.models import ExternalBeneficiary, Journey, WorkflowKind

from .beneficiary_services import issue_access_for_holder
from .models import Access, CredentialStatus


User = get_user_model()


@skipUnless(connection.vendor == "postgresql", "Ce test exerce l’idempotence Access PostgreSQL réelle.")
class Task25AccessIssueConcurrencyTests(TransactionTestCase):
    reset_sequences = False

    def setUp(self):
        self.buyer = User.objects.create_user(
            username="t25-access-race",
            email="t25-access-race@example.test",
            password="Access-2026!",
        )
        self.activity = Activity.objects.create(
            owner_profile=self.buyer,
            created_by=self.buyer,
            title="T25 Access Race",
        )
        self.occurrence = Occurrence.objects.create(
            activity=self.activity,
            start_at=timezone.now() + timedelta(days=1),
            end_at=timezone.now() + timedelta(days=1, hours=1),
        )
        self.external = create_external_beneficiary(
            created_by=self.buyer,
            display_name="Jacques Race T25",
            email="jacques-race@example.test",
        )
        self.journey = create_journey_for_holder(
            initiated_by=self.buyer,
            external_beneficiary=self.external,
            activity=self.activity,
            occurrence=self.occurrence,
            workflow=WorkflowKind.RESERVATION,
        )

    def _issue(self, barrier):
        close_old_connections()
        try:
            barrier.wait(timeout=5)
            activity = Activity.objects.get(pk=self.activity.pk)
            occurrence = Occurrence.objects.get(pk=self.occurrence.pk)
            journey = Journey.objects.get(pk=self.journey.pk)
            external = ExternalBeneficiary.objects.get(pk=self.external.pk)
            access = issue_access_for_holder(
                external_beneficiary=external,
                activity=activity,
                occurrence=occurrence,
                journey=journey,
                source_key="t25-concurrent-external-ticket",
                single_use=True,
            )
            return str(access.pk)
        finally:
            connection.close()

    def test_two_concurrent_issuances_return_one_access_and_one_active_credential(self):
        barrier = Barrier(2)
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(self._issue, barrier) for _ in range(2)]
            access_ids = [future.result(timeout=15) for future in futures]

        self.assertEqual(len(set(access_ids)), 1)
        accesses = Access.objects.filter(
            journey=self.journey,
            source_key="t25-concurrent-external-ticket",
        )
        self.assertEqual(accesses.count(), 1)
        access = accesses.get()
        self.assertEqual(access.external_beneficiary_id, self.external.pk)
        self.assertEqual(access.credentials.filter(status=CredentialStatus.ACTIVE).count(), 1)
