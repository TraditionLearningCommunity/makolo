import threading
from unittest import skipUnless

from django.contrib.auth import get_user_model
from django.db import close_old_connections, connection, connections
from django.test import TransactionTestCase

from activities.models import Activity
from authorization.services import grant_activity_role
from journeys.collaboration_models import JourneyAssignmentResponsibility
from journeys.collaboration_services import assign_journey
from opportunities.models import OpportunityKind, OpportunityRequirementKind, OpportunitySourceType
from opportunities.services import (
    add_requirement,
    create_opportunity,
    create_opportunity_revision,
    create_opportunity_source,
    publish_opportunity_revision,
)
from requirements.contracts import RequirementAssessmentState

from .models import OpportunityPolicy, ServiceKind, ServiceRequirementAssessment
from .requirement_services import assess_requirement
from .services import create_service_details, create_service_journey


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

    threads = [threading.Thread(target=worker, args=(first,)), threading.Thread(target=worker, args=(second,))]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=20)
    if any(thread.is_alive() for thread in threads):
        raise AssertionError("Concurrent T34A assessment worker did not terminate.")
    return outcomes


@skipUnless(connection.vendor == "postgresql", "T34A assessment concurrency requires PostgreSQL")
class ServiceRequirementAssessmentConcurrencyTests(TransactionTestCase):
    reset_sequences = False
    serialized_rollback = True

    def setUp(self):
        self.curator = User.objects.create_user(username="t34a-conc-curator", email="t34a-conc-curator@example.com", password="x", is_staff=True, is_superuser=True)
        self.manager = User.objects.create_user(username="t34a-conc-manager", email="t34a-conc-manager@example.com", password="x")
        self.beneficiary = User.objects.create_user(username="t34a-conc-beneficiary", email="t34a-conc-beneficiary@example.com", password="x")
        activity = Activity.objects.create(owner_profile=self.manager, created_by=self.manager, title="T34A concurrency service")
        grant_activity_role(profile=self.manager, activity=activity)
        service = create_service_details(
            activity=activity,
            actor=self.manager,
            service_kind=ServiceKind.APPLICATION_SUPPORT,
            opportunity_policy=OpportunityPolicy.REQUIRED,
        )
        opportunity = create_opportunity(actor=self.curator, kind=OpportunityKind.JOB)
        revision = create_opportunity_revision(
            opportunity=opportunity,
            actor=self.curator,
            title="T34A concurrent assessment",
            issuer_name="Issuer",
            timezone_name="Africa/Lubumbashi",
        )
        create_opportunity_source(
            opportunity=opportunity,
            actor=self.curator,
            source_type=OpportunitySourceType.OFFICIAL,
            source_name="T34A concurrency source",
            url=f"https://example.test/t34a-concurrency/{opportunity.pk}",
            is_primary=True,
            verified=True,
        )
        add_requirement(
            revision=revision,
            actor=self.curator,
            kind=OpportunityRequirementKind.ELIGIBILITY,
            title="Concurrent eligibility",
            position=10,
        )
        publish_opportunity_revision(opportunity=opportunity, revision=revision, actor=self.curator)
        journey = create_service_journey(
            service=service,
            initiated_by=self.beneficiary,
            beneficiary=self.beneficiary,
            opportunity=opportunity,
        )
        assign_journey(
            journey=journey,
            profile=self.manager,
            responsibility=JourneyAssignmentResponsibility.LEAD,
            is_primary=True,
            assigned_by=self.manager,
        )
        self.assessment = journey.service_context.requirement_assessments.get()

    def test_concurrent_assessments_serialize_without_corrupting_audit(self):
        assessment_id = self.assessment.pk
        manager_id = self.manager.pk

        def evaluate(state):
            assessment = ServiceRequirementAssessment.objects.get(pk=assessment_id)
            manager = User.objects.get(pk=manager_id)
            result = assess_requirement(assessment=assessment, actor=manager, status=state, note=f"concurrent:{state}")
            return result.status

        outcomes = run_pair(
            lambda: evaluate(RequirementAssessmentState.PENDING),
            lambda: evaluate(RequirementAssessmentState.UNSATISFIED),
        )
        self.assertEqual(sum(kind == "ok" for kind, _ in outcomes), 2)
        self.assessment.refresh_from_db()
        self.assertIn(
            self.assessment.status,
            {RequirementAssessmentState.PENDING, RequirementAssessmentState.UNSATISFIED},
        )
        self.assertEqual(self.assessment.assessed_by_id, self.manager.pk)
        self.assertIsNotNone(self.assessment.assessed_at)
        self.assertIn(self.assessment.note, {"concurrent:pending", "concurrent:unsatisfied"})
