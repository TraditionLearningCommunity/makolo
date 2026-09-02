import threading
from unittest import skipUnless

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db import close_old_connections, connection, connections
from django.test import TestCase, TransactionTestCase
from django.utils import timezone

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
from .models import JourneyShareAcceptance, ShareEnvelope, ShareStatus
from .services import ShareUnavailable, revoke_share_link


User = get_user_model()


def build_journey_share_fixture(*, suffix):
    sender = User.objects.create_user(
        username=f"p5-race-sender-{suffix}",
        email=f"p5-race-sender-{suffix}@example.test",
        password="pass",
    )
    recipient = User.objects.create_user(
        username=f"p5-race-recipient-{suffix}",
        email=f"p5-race-recipient-{suffix}@example.test",
        password="pass",
    )
    replacement = User.objects.create_user(
        username=f"p5-race-replacement-{suffix}",
        email=f"p5-race-replacement-{suffix}@example.test",
        password="pass",
    )
    sender_profile = UserProfile.objects.create(user=sender, searchable=True)
    recipient_profile = UserProfile.objects.create(user=recipient, searchable=True)
    UserProfile.objects.create(user=replacement, searchable=True)

    activity = Activity.objects.create(
        owner_profile=sender,
        created_by=sender,
        title=f"P5 Journey hardening {suffix}",
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
        key=f"p5-hardening-{suffix}",
        name="P5 hardening path",
        created_by=sender,
    )
    ServicePlanTemplateStep.objects.create(template=template, title="Prepare", position=10)
    template.status = ServicePlanTemplateStatus.PUBLISHED
    template.save(update_fields=["status", "updated_at"])

    source = Journey.objects.create(
        initiated_by=sender,
        beneficiary=sender,
        activity=activity,
        workflow=WorkflowKind.SERVICE,
    )
    ServiceJourneyContext.objects.create(journey=source, service_plan_template=template)
    created = create_direct_journey_share(
        created_by=sender,
        recipient=recipient_profile,
        journey=source,
    )
    return {
        "sender": sender,
        "recipient": recipient,
        "replacement": replacement,
        "sender_profile": sender_profile,
        "recipient_profile": recipient_profile,
        "activity": activity,
        "source": source,
        "created": created,
    }


class P5JourneyLifecycleTests(TestCase):
    def test_recent_duplicate_revalidates_source_ownership(self):
        fixture = build_journey_share_fixture(suffix="ownership")
        fixture["source"].beneficiary = fixture["replacement"]
        fixture["source"].save(update_fields=["beneficiary", "updated_at"])

        with self.assertRaises(PermissionDenied):
            create_direct_journey_share(
                created_by=fixture["sender"],
                recipient=fixture["recipient_profile"],
                journey=fixture["source"],
            )

        self.assertEqual(fixture["source"].share_subjects.count(), 1)

    def test_expired_journey_share_cannot_materialize(self):
        fixture = build_journey_share_fixture(suffix="expired")
        envelope = fixture["created"].envelope
        envelope.expires_at = timezone.now() - timezone.timedelta(seconds=1)
        envelope.save(update_fields=["expires_at", "updated_at"])

        with self.assertRaises(ShareUnavailable):
            accept_journey_share(
                delivery_id=fixture["created"].delivery.pk,
                user=fixture["recipient"],
            )

        self.assertFalse(
            Journey.objects.filter(
                beneficiary=fixture["recipient"],
                activity=fixture["activity"],
            ).exists()
        )
        self.assertFalse(
            JourneyShareAcceptance.objects.filter(delivery=fixture["created"].delivery).exists()
        )

    def test_revocation_after_acceptance_keeps_destination_journey(self):
        fixture = build_journey_share_fixture(suffix="accepted")
        accepted = accept_journey_share(
            delivery_id=fixture["created"].delivery.pk,
            user=fixture["recipient"],
        )

        revoke_share_link(envelope=fixture["created"].envelope, actor=fixture["sender"])
        fixture["created"].envelope.refresh_from_db()

        self.assertEqual(fixture["created"].envelope.status, ShareStatus.REVOKED)
        self.assertTrue(Journey.objects.filter(pk=accepted.journey.pk).exists())
        self.assertTrue(
            JourneyShareAcceptance.objects.filter(
                delivery=fixture["created"].delivery,
                resulting_journey=accepted.journey,
            ).exists()
        )


def run_accept_revoke_race(*, accept, revoke):
    barrier = threading.Barrier(2)
    outcomes = {}
    lock = threading.Lock()

    def worker(name, fn):
        close_old_connections()
        try:
            barrier.wait(timeout=10)
            outcome = ("ok", fn())
        except Exception as exc:
            outcome = ("error", exc)
        finally:
            connections.close_all()
        with lock:
            outcomes[name] = outcome

    threads = [
        threading.Thread(target=worker, args=("accept", accept)),
        threading.Thread(target=worker, args=("revoke", revoke)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=20)
    if any(thread.is_alive() for thread in threads):
        raise AssertionError("Concurrent P5 accept/revoke worker did not terminate.")
    return outcomes


@skipUnless(connection.vendor == "postgresql", "P5 Journey accept/revoke race requires PostgreSQL")
class P5JourneyRevocationRaceTests(TransactionTestCase):
    serialized_rollback = True

    def setUp(self):
        fixture = build_journey_share_fixture(suffix="postgres")
        self.sender_id = fixture["sender"].pk
        self.recipient_id = fixture["recipient"].pk
        self.activity_id = fixture["activity"].pk
        self.delivery_id = fixture["created"].delivery.pk
        self.envelope_id = fixture["created"].envelope.pk

    def test_accept_and_revoke_race_has_one_consistent_terminal_state(self):
        def accept():
            recipient = User.objects.get(pk=self.recipient_id)
            return accept_journey_share(delivery_id=self.delivery_id, user=recipient).journey.pk

        def revoke():
            sender = User.objects.get(pk=self.sender_id)
            envelope = ShareEnvelope.objects.get(pk=self.envelope_id)
            return revoke_share_link(envelope=envelope, actor=sender).pk

        outcomes = run_accept_revoke_race(accept=accept, revoke=revoke)
        self.assertEqual(outcomes["revoke"][0], "ok", outcomes)

        envelope = ShareEnvelope.objects.get(pk=self.envelope_id)
        destinations = Journey.objects.filter(
            beneficiary_id=self.recipient_id,
            activity_id=self.activity_id,
        )
        acceptances = JourneyShareAcceptance.objects.filter(delivery_id=self.delivery_id)

        self.assertEqual(envelope.status, ShareStatus.REVOKED)
        self.assertLessEqual(destinations.count(), 1)
        self.assertEqual(acceptances.count(), destinations.count())

        if outcomes["accept"][0] == "ok":
            self.assertEqual(destinations.count(), 1, outcomes)
            self.assertEqual(destinations.get().pk, outcomes["accept"][1])
        else:
            self.assertIsInstance(outcomes["accept"][1], ShareUnavailable, outcomes)
            self.assertEqual(destinations.count(), 0, outcomes)
