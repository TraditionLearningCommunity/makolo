import threading
from unittest import skipUnless

from django.contrib.auth import get_user_model
from django.db import close_old_connections, connection, connections
from django.test import TransactionTestCase

from accounts.models import UserProfile
from activities.models import Activity, ActivityStatus, ActivityVisibility
from journeys.models import Journey, WorkflowKind
from services.models import (
    OpportunityPolicy,
    ServiceDetails,
    ServiceJourneyContext,
    ServiceKind,
    ServicePlanTemplate,
    ServicePlanTemplateStatus,
    ServicePlanTemplateStep,
)

from .journey_reuse import accept_journey_share, create_direct_journey_share
from .models import JourneyShareAcceptance


User = get_user_model()


def run_pair(first, second):
    barrier = threading.Barrier(2)
    outcomes = []
    outcome_lock = threading.Lock()

    def worker(fn):
        close_old_connections()
        try:
            barrier.wait(timeout=10)
            outcome = ("ok", fn())
        except Exception as exc:
            outcome = ("error", exc)
        finally:
            connections.close_all()
        with outcome_lock:
            outcomes.append(outcome)

    threads = [threading.Thread(target=worker, args=(first,)), threading.Thread(target=worker, args=(second,))]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=20)
    if any(thread.is_alive() for thread in threads):
        raise AssertionError("Concurrent Journey reuse worker did not terminate.")
    return outcomes


@skipUnless(connection.vendor == "postgresql", "P3 Journey reuse concurrency requires PostgreSQL")
class JourneyReuseConcurrencyTests(TransactionTestCase):
    reset_sequences = False
    serialized_rollback = True

    def setUp(self):
        self.sender = User.objects.create_user(username="p3-concurrency-sender", email="p3-concurrency-sender@makolo.test", password="x")
        self.recipient = User.objects.create_user(username="p3-concurrency-recipient", email="p3-concurrency-recipient@makolo.test", password="x")
        UserProfile.objects.create(user=self.sender, searchable=True)
        recipient_profile = UserProfile.objects.create(user=self.recipient, searchable=True)
        activity = Activity.objects.create(
            owner_profile=self.sender,
            created_by=self.sender,
            title="P3 concurrency service",
            status=ActivityStatus.PUBLISHED,
            visibility=ActivityVisibility.PUBLIC,
        )
        service = ServiceDetails.objects.create(
            activity=activity,
            service_kind=ServiceKind.CAREER_SUPPORT,
            opportunity_policy=OpportunityPolicy.NONE,
        )
        template = ServicePlanTemplate.objects.create(
            service=service,
            key="reuse-concurrency",
            name="Reuse concurrency",
            created_by=self.sender,
        )
        ServicePlanTemplateStep.objects.create(template=template, title="Step A", position=10)
        ServicePlanTemplateStep.objects.create(template=template, title="Step B", position=20)
        template.status = ServicePlanTemplateStatus.PUBLISHED
        template.save(update_fields=["status", "updated_at"])
        source = Journey.objects.create(
            initiated_by=self.sender,
            beneficiary=self.sender,
            activity=activity,
            workflow=WorkflowKind.SERVICE,
        )
        ServiceJourneyContext.objects.create(journey=source, service_plan_template=template)
        created = create_direct_journey_share(created_by=self.sender, recipient=recipient_profile, journey=source)
        self.delivery_id = created.delivery.pk
        self.activity_id = activity.pk
        self.recipient_id = self.recipient.pk

    def test_two_simultaneous_accepts_create_one_destination_journey(self):
        def accept():
            user = User.objects.get(pk=self.recipient_id)
            return accept_journey_share(delivery_id=self.delivery_id, user=user).journey.pk

        outcomes = run_pair(accept, accept)
        self.assertEqual(sum(kind == "ok" for kind, _ in outcomes), 2, outcomes)
        journey_ids = {value for kind, value in outcomes if kind == "ok"}
        self.assertEqual(len(journey_ids), 1)
        self.assertEqual(
            Journey.objects.filter(beneficiary_id=self.recipient_id, activity_id=self.activity_id).count(),
            1,
        )
        self.assertEqual(JourneyShareAcceptance.objects.filter(delivery_id=self.delivery_id).count(), 1)
