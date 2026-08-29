import threading
from unittest import skipUnless

from django.contrib.auth import get_user_model
from django.db import close_old_connections, connection, connections
from django.test import TransactionTestCase

from activities.models import Activity
from authorization.constants import SystemRoleCode
from authorization.services import grant_activity_role
from journeys.collaboration_models import JourneyAssignmentResponsibility
from journeys.collaboration_services import assign_journey
from opportunities.models import OpportunityKind, OpportunitySourceType
from opportunities.services import create_opportunity, create_opportunity_revision, create_opportunity_source, publish_opportunity_revision

from .models import OpportunityPolicy, ServiceKind, ServiceJourneyContext
from .services import adopt_opportunity_revision, create_service_details, create_service_journey


User = get_user_model()


def run_pair(first, second):
    barrier = threading.Barrier(2)
    outcomes = []
    lock = threading.Lock()

    def worker(fn):
        close_old_connections()
        try:
            barrier.wait(timeout=10)
            value = fn()
            outcome = ("ok", value)
        except Exception as exc:
            outcome = ("error", exc)
        finally:
            connections.close_all()
        with lock:
            outcomes.append(outcome)

    threads = [threading.Thread(target=worker, args=(first,)), threading.Thread(target=worker, args=(second,))]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=20)
    if any(thread.is_alive() for thread in threads):
        raise AssertionError("Concurrent T32 worker did not terminate.")
    return outcomes


@skipUnless(connection.vendor == "postgresql", "T32 concurrency requires PostgreSQL")
class ServiceOpportunityConcurrencyTests(TransactionTestCase):
    reset_sequences = False
    serialized_rollback = True

    def setUp(self):
        self.curator = User.objects.create_user(username="t32-concurrency-curator", email="t32-concurrency-curator@example.com", password="x", is_superuser=True, is_staff=True)
        self.manager = User.objects.create_user(username="t32-concurrency-manager", email="t32-concurrency-manager@example.com", password="x")
        self.beneficiary = User.objects.create_user(username="t32-concurrency-beneficiary", email="t32-concurrency-beneficiary@example.com", password="x")
        self.activity = Activity.objects.create(owner_profile=self.manager, created_by=self.manager, title="T32 concurrency service")
        grant_activity_role(profile=self.manager, activity=self.activity, role_code=SystemRoleCode.ACTIVITY_SERVICE_MANAGER)
        self.service = create_service_details(activity=self.activity, actor=self.manager, service_kind=ServiceKind.APPLICATION_SUPPORT, opportunity_policy=OpportunityPolicy.REQUIRED)
        self.opportunity = create_opportunity(actor=self.curator, kind=OpportunityKind.JOB)
        revision1 = create_opportunity_revision(opportunity=self.opportunity, actor=self.curator, title="Opportunity v1", issuer_name="Issuer", timezone_name="Africa/Lubumbashi")
        create_opportunity_source(opportunity=self.opportunity, actor=self.curator, source_type=OpportunitySourceType.OFFICIAL, source_name="Official", url="https://example.test/t32-concurrency", is_primary=True)
        publish_opportunity_revision(opportunity=self.opportunity, revision=revision1, actor=self.curator)
        self.revision1 = revision1
        self.journey = create_service_journey(service=self.service, initiated_by=self.beneficiary, beneficiary=self.beneficiary, opportunity=self.opportunity)
        assign_journey(journey=self.journey, profile=self.manager, responsibility=JourneyAssignmentResponsibility.LEAD, is_primary=True, assigned_by=self.manager)

    def test_concurrent_revision_creation_serializes_versions(self):
        opportunity_id = self.opportunity.pk

        def create(title):
            from opportunities.models import Opportunity
            return create_opportunity_revision(opportunity=Opportunity.objects.get(pk=opportunity_id), actor=self.curator, title=title, issuer_name="Issuer", timezone_name="Africa/Lubumbashi").version

        outcomes = run_pair(lambda: create("v2-a"), lambda: create("v2-b"))
        self.assertEqual(sum(kind == "ok" for kind, _ in outcomes), 2)
        self.assertEqual(list(self.opportunity.revisions.order_by("version").values_list("version", flat=True)), [1, 2, 3])

    def test_concurrent_revision_adoption_never_regresses_pinned_version(self):
        revision2 = create_opportunity_revision(opportunity=self.opportunity, actor=self.curator, title="Opportunity v2", issuer_name="Issuer", timezone_name="Africa/Lubumbashi")
        publish_opportunity_revision(opportunity=self.opportunity, revision=revision2, actor=self.curator)
        revision3 = create_opportunity_revision(opportunity=self.opportunity, actor=self.curator, title="Opportunity v3", issuer_name="Issuer", timezone_name="Africa/Lubumbashi")
        publish_opportunity_revision(opportunity=self.opportunity, revision=revision3, actor=self.curator)

        context = self.journey.service_context
        self.assertEqual(context.opportunity_revision_id, self.revision1.pk)
        context_id = context.pk

        def adopt(revision):
            current = ServiceJourneyContext.objects.get(pk=context_id)
            result = adopt_opportunity_revision(context=current, revision=revision, actor=self.manager)
            return result.opportunity_revision.version

        outcomes = run_pair(lambda: adopt(revision2), lambda: adopt(revision3))
        context.refresh_from_db()
        self.assertEqual(context.opportunity_revision.version, 3)
        self.assertGreaterEqual(sum(kind == "ok" for kind, _ in outcomes), 1)
