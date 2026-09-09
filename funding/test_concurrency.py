import threading
from decimal import Decimal
from unittest import skipUnless

from django.contrib.auth import get_user_model
from django.db import close_old_connections, connection, connections
from django.test import TransactionTestCase

from activities.models import ActivityStatus, ActivityVisibility

from .models import FundingContribution
from .services import create_funding, create_funding_contribution


User = get_user_model()


def run_pair(first, second):
    barrier = threading.Barrier(2)
    outcomes = []
    lock = threading.Lock()

    def worker(fn):
        close_old_connections()
        try:
            barrier.wait(timeout=10)
            result = fn()
            outcome = ("ok", result)
        except Exception as exc:
            outcome = ("error", exc)
        finally:
            connections.close_all()
        with lock:
            outcomes.append(outcome)

    threads = [
        threading.Thread(target=worker, args=(first,)),
        threading.Thread(target=worker, args=(second,)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=25)
    if any(thread.is_alive() for thread in threads):
        raise AssertionError("Concurrent funding worker did not terminate.")
    return outcomes


@skipUnless(connection.vendor == "postgresql", "Funding concurrency requires PostgreSQL")
class FundingContributionConcurrencyTests(TransactionTestCase):
    serialized_rollback = True
    reset_sequences = False

    def setUp(self):
        self.owner = User.objects.create_user(
            username="funding-concurrency-owner",
            email="funding-concurrency-owner@example.test",
            password="x",
        )
        self.contributor = User.objects.create_user(
            username="funding-concurrency-contributor",
            email="funding-concurrency-contributor@example.test",
            password="x",
        )
        self.funding = create_funding(
            actor=self.owner,
            title="Funding concurrency",
            currency="USD",
            target_amount=Decimal("100.00"),
            status=ActivityStatus.PUBLISHED,
            visibility=ActivityVisibility.PUBLIC,
        )

    def contribution_attempt(self):
        from .models import FundingDetails

        funding = FundingDetails.objects.get(pk=self.funding.pk)
        actor = User.objects.get(pk=self.contributor.pk)
        contribution = create_funding_contribution(
            funding=funding,
            actor=actor,
            amount=Decimal("25.00"),
            client_reference="same-client-reference",
        )
        return contribution.pk

    def test_same_client_reference_converges_to_one_contribution_and_obligation(self):
        outcomes = run_pair(self.contribution_attempt, self.contribution_attempt)

        self.assertEqual(sum(kind == "ok" for kind, _ in outcomes), 2, outcomes)
        contribution_ids = {value for kind, value in outcomes if kind == "ok"}
        self.assertEqual(len(contribution_ids), 1)
        contributions = FundingContribution.objects.filter(
            funding=self.funding,
            contributor_profile=self.contributor,
            client_reference="same-client-reference",
        )
        self.assertEqual(contributions.count(), 1)
        contribution = contributions.get()
        self.assertIsNotNone(contribution.payment_obligation_id)
        self.assertEqual(
            FundingContribution.objects.filter(
                payment_obligation_id=contribution.payment_obligation_id
            ).count(),
            1,
        )
