import threading
from datetime import timedelta
from unittest import skipUnless

from django.contrib.auth import get_user_model
from django.db import close_old_connections, connection, connections
from django.test import TransactionTestCase
from django.utils import timezone

from activities.models import Activity
from authorization.constants import SystemRoleCode
from authorization.services import grant_activity_role
from journeys.collaboration_models import JourneyAssignmentResponsibility
from journeys.collaboration_services import assign_journey

from .models import ServiceCurrentOutcome, ServiceJourneyContext, ServiceKind, ServiceOutcomeEventType, ServiceSubmission, ServiceSubmissionMode, ServiceSubmissionStatus
from .services import create_service_details, create_service_journey
from .t33_services import fail_service_submission, prepare_service_submission, record_service_outcome, submit_service_submission


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
        thread.join(timeout=25)
    if any(thread.is_alive() for thread in threads):
        raise AssertionError("Concurrent T33 Services worker did not terminate.")
    return outcomes


@skipUnless(connection.vendor == "postgresql", "T33 Services concurrency requires PostgreSQL")
class ServiceSubmissionOutcomeConcurrencyTests(TransactionTestCase):
    serialized_rollback = True
    reset_sequences = False

    def setUp(self):
        self.manager = User.objects.create_user(username="t33-services-conc-manager", email="t33-services-conc-manager@example.com", password="x")
        self.beneficiary = User.objects.create_user(username="t33-services-conc-beneficiary", email="t33-services-conc-beneficiary@example.com", password="x")
        activity = Activity.objects.create(owner_profile=self.manager, created_by=self.manager, title="T33 Services concurrency")
        grant_activity_role(profile=self.manager, activity=activity, role_code=SystemRoleCode.ACTIVITY_SERVICE_MANAGER)
        service = create_service_details(activity=activity, actor=self.manager, service_kind=ServiceKind.APPLICATION_SUPPORT)
        journey = create_service_journey(service=service, initiated_by=self.beneficiary, beneficiary=self.beneficiary)
        assign_journey(journey=journey, profile=self.manager, responsibility=JourneyAssignmentResponsibility.LEAD, is_primary=True, assigned_by=self.manager)
        self.context = journey.service_context

    def prepare(self, mode):
        context = ServiceJourneyContext.objects.get(pk=self.context.pk)
        actor = User.objects.get(pk=self.manager.pk)
        return prepare_service_submission(context=context, actor=actor, mode=mode).attempt

    def test_concurrent_next_attempt_numbers_are_unique_and_sequential(self):
        outcomes = run_pair(lambda: self.prepare(ServiceSubmissionMode.EMAIL), lambda: self.prepare(ServiceSubmissionMode.EXTERNAL_WEB))
        self.assertEqual(sum(kind == "ok" for kind, _ in outcomes), 2)
        self.assertEqual(list(ServiceSubmission.objects.filter(context=self.context).order_by("attempt").values_list("attempt", flat=True)), [1, 2])

    def test_concurrent_submission_transitions_leave_one_valid_terminal_direction(self):
        submission = prepare_service_submission(context=self.context, actor=self.manager, mode=ServiceSubmissionMode.EMAIL)
        submission_id = submission.pk

        def submit():
            return submit_service_submission(submission=ServiceSubmission.objects.get(pk=submission_id), actor=User.objects.get(pk=self.manager.pk)).status

        def fail():
            return fail_service_submission(submission=ServiceSubmission.objects.get(pk=submission_id), actor=User.objects.get(pk=self.manager.pk), failure_reason="Concurrent failure").status

        outcomes = run_pair(submit, fail)
        submission.refresh_from_db()
        self.assertIn(submission.status, {ServiceSubmissionStatus.SUBMITTED, ServiceSubmissionStatus.FAILED})
        self.assertEqual(sum(kind == "ok" for kind, _ in outcomes), 1)

    def test_concurrent_outcomes_project_chronologically_newest_event(self):
        old_time = timezone.now()
        new_time = old_time + timedelta(minutes=5)

        def record(kind, when):
            context = ServiceJourneyContext.objects.get(pk=self.context.pk)
            actor = User.objects.get(pk=self.manager.pk)
            return record_service_outcome(context=context, actor=actor, event_type=kind, occurred_at=when).pk

        outcomes = run_pair(
            lambda: record(ServiceOutcomeEventType.UNDER_REVIEW, old_time),
            lambda: record(ServiceOutcomeEventType.INTERVIEW, new_time),
        )
        self.assertEqual(sum(kind == "ok" for kind, _ in outcomes), 2)
        self.context.refresh_from_db()
        self.assertEqual(self.context.current_outcome, ServiceCurrentOutcome.INTERVIEW)
