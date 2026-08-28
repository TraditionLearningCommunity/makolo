import threading
from unittest import skipUnless

from django.contrib.auth import get_user_model
from django.db import close_old_connections, connection
from django.test import TransactionTestCase

from activities.models import Activity
from authorization.services import grant_activity_role
from journeys.collaboration_models import JourneyAssignmentResponsibility
from journeys.collaboration_services import assign_journey

from .models import OpportunityPolicy, ServiceKind, ServicePlanMaterialization
from .services import add_template_step, create_plan_template, create_service_details, create_service_journey, materialize_service_plan, publish_plan_template, submit_service_journey


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
            close_old_connections()
        with lock:
            outcomes.append(outcome)

    threads = [threading.Thread(target=worker, args=(first,)), threading.Thread(target=worker, args=(second,))]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=20)
    if any(thread.is_alive() for thread in threads):
        raise AssertionError("Concurrent Services worker did not terminate.")
    return outcomes


@skipUnless(connection.vendor == "postgresql", "T31 materialization concurrency requires PostgreSQL")
class ServiceMaterializationConcurrencyTests(TransactionTestCase):
    reset_sequences = False
    serialized_rollback = True

    def setUp(self):
        self.manager = User.objects.create_user(username="services-concurrency-manager", email="services-concurrency-manager@example.com", password="x")
        self.beneficiary = User.objects.create_user(username="services-concurrency-beneficiary", email="services-concurrency-beneficiary@example.com", password="x")
        self.activity = Activity.objects.create(owner_profile=self.manager, created_by=self.manager, title="Services materialization concurrency")
        grant_activity_role(profile=self.manager, activity=self.activity)
        self.service = create_service_details(activity=self.activity, actor=self.manager, service_kind=ServiceKind.CAREER_SUPPORT, opportunity_policy=OpportunityPolicy.NONE)
        template = create_plan_template(service=self.service, actor=self.manager, key="concurrency", name="Concurrency plan")
        add_template_step(template=template, actor=self.manager, title="Step A", position=10)
        add_template_step(template=template, actor=self.manager, title="Step B", position=20)
        self.template = publish_plan_template(template=template, actor=self.manager)
        self.journey = create_service_journey(service=self.service, initiated_by=self.beneficiary, beneficiary=self.beneficiary, template=self.template)
        assign_journey(journey=self.journey, profile=self.manager, responsibility=JourneyAssignmentResponsibility.LEAD, is_primary=True, assigned_by=self.manager)
        submit_service_journey(journey=self.journey, actor=self.beneficiary)

    def test_two_materializations_create_one_snapshot(self):
        context_id = self.journey.service_context.pk
        from .models import ServiceJourneyContext
        outcomes = run_pair(
            lambda: materialize_service_plan(context=ServiceJourneyContext.objects.get(pk=context_id), actor=self.manager),
            lambda: materialize_service_plan(context=ServiceJourneyContext.objects.get(pk=context_id), actor=self.manager),
        )
        context = ServiceJourneyContext.objects.get(pk=context_id)
        self.assertIsNotNone(context.plan_materialized_at)
        self.assertEqual(self.journey.steps.count(), 2)
        self.assertEqual(ServicePlanMaterialization.objects.filter(context=context).count(), 2)
        self.assertEqual(sum(kind == "ok" for kind, _ in outcomes), 2)
