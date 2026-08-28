import threading
from unittest import skipUnless

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import close_old_connections, connection
from django.test import TransactionTestCase

from activities.models import Activity
from authorization.services import grant_activity_role

from .collaboration_models import (
    JourneyArtifactKind,
    JourneyArtifactReview,
    JourneyArtifactReviewStatus,
    JourneyArtifactStatus,
    JourneyAssignment,
    JourneyAssignmentResponsibility,
    JourneyAssignmentStatus,
    JourneyBlockerStatus,
    JourneyStepStatus,
)
from .collaboration_services import (
    assign_journey,
    complete_step,
    create_artifact,
    create_artifact_version,
    create_blocker,
    create_step,
    decide_artifact_review,
    end_journey_assignment,
    mark_ready,
    request_artifact_review,
    resolve_blocker,
    start_step,
)
from .models import Journey, JourneyStatus, WorkflowKind
from .services import confirm_journey, create_journey, start_journey, submit_journey


User = get_user_model()


def pdf_upload(text):
    return SimpleUploadedFile("cv.pdf", b"%PDF-1.4\n" + text + b"\n%%EOF", content_type="application/pdf")


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
        raise AssertionError("Concurrent T31 worker did not terminate.")
    return outcomes


@skipUnless(connection.vendor == "postgresql", "T31 concurrency invariants require PostgreSQL row locks")
class JourneyTask31ConcurrencyTests(TransactionTestCase):
    reset_sequences = False

    def setUp(self):
        self.manager = User.objects.create_user(username="t31-concurrency-manager", email="t31-concurrency-manager@example.com", password="x")
        self.reviewer = User.objects.create_user(username="t31-concurrency-reviewer", email="t31-concurrency-reviewer@example.com", password="x")
        self.support = User.objects.create_user(username="t31-concurrency-support", email="t31-concurrency-support@example.com", password="x")
        self.beneficiary = User.objects.create_user(username="t31-concurrency-beneficiary", email="t31-concurrency-beneficiary@example.com", password="x")
        self.activity = Activity.objects.create(owner_profile=self.manager, created_by=self.manager, title="T31 concurrency")
        grant_activity_role(profile=self.manager, activity=self.activity)
        grant_activity_role(profile=self.reviewer, activity=self.activity)
        self.journey = create_journey(initiated_by=self.beneficiary, beneficiary=self.beneficiary, activity=self.activity, workflow=WorkflowKind.SERVICE)
        self.lead = assign_journey(journey=self.journey, profile=self.manager, responsibility=JourneyAssignmentResponsibility.LEAD, is_primary=True, assigned_by=self.manager)

    def _confirmed_service_journey(self):
        journey = create_journey(initiated_by=self.beneficiary, beneficiary=self.beneficiary, activity=self.activity, workflow=WorkflowKind.SERVICE)
        submit_journey(journey=journey, actor=self.beneficiary)
        confirm_journey(journey=journey, actor=self.beneficiary)
        return journey

    def test_two_simultaneous_journey_starts_leave_one_transition(self):
        journey = self._confirmed_service_journey()
        outcomes = run_pair(
            lambda: start_journey(journey=Journey.objects.get(pk=journey.pk), actor=self.manager),
            lambda: start_journey(journey=Journey.objects.get(pk=journey.pk), actor=self.manager),
        )
        journey.refresh_from_db()
        self.assertEqual(journey.status, JourneyStatus.IN_PROGRESS)
        self.assertEqual(journey.transitions.filter(to_status=JourneyStatus.IN_PROGRESS).count(), 1)
        self.assertEqual(sum(kind == "ok" for kind, _ in outcomes), 1)
        self.assertTrue(any(isinstance(value, ValidationError) for kind, value in outcomes if kind == "error"))

    def test_two_complete_step_calls_are_idempotent(self):
        step = create_step(journey=self.journey, title="Concurrent complete", created_by=self.manager)
        mark_ready(step=step, actor=self.manager)
        start_step(step=step, actor=self.manager)
        outcomes = run_pair(
            lambda: complete_step(step=type(step).objects.get(pk=step.pk), actor=self.manager),
            lambda: complete_step(step=type(step).objects.get(pk=step.pk), actor=self.manager),
        )
        step.refresh_from_db()
        self.assertEqual(step.status, JourneyStepStatus.COMPLETED)
        self.assertEqual(sum(kind == "ok" for kind, _ in outcomes), 2)

    def test_two_primary_leads_cannot_survive(self):
        end_journey_assignment(assignment=self.lead, actor=self.manager)
        outcomes = run_pair(
            lambda: assign_journey(journey=Journey.objects.get(pk=self.journey.pk), profile=self.reviewer, responsibility=JourneyAssignmentResponsibility.LEAD, is_primary=True, assigned_by=self.manager),
            lambda: assign_journey(journey=Journey.objects.get(pk=self.journey.pk), profile=self.support, responsibility=JourneyAssignmentResponsibility.LEAD, is_primary=True, assigned_by=self.manager),
        )
        active = JourneyAssignment.objects.filter(journey=self.journey, responsibility=JourneyAssignmentResponsibility.LEAD, is_primary=True, status=JourneyAssignmentStatus.ACTIVE)
        self.assertEqual(active.count(), 1)
        self.assertEqual(sum(kind == "ok" for kind, _ in outcomes), 1)
        self.assertEqual(sum(kind == "error" for kind, _ in outcomes), 1)

    def test_last_blocker_resolution_is_safe_under_concurrency(self):
        step = create_step(journey=self.journey, title="Blocked", created_by=self.manager)
        mark_ready(step=step, actor=self.manager)
        start_step(step=step, actor=self.manager)
        blocker = create_blocker(journey=self.journey, step=step, title="Concurrent blocker", actor=self.manager)
        outcomes = run_pair(
            lambda: resolve_blocker(blocker=type(blocker).objects.get(pk=blocker.pk), actor=self.manager, resolution_note="resolved A"),
            lambda: resolve_blocker(blocker=type(blocker).objects.get(pk=blocker.pk), actor=self.manager, resolution_note="resolved B"),
        )
        blocker.refresh_from_db(); step.refresh_from_db()
        self.assertEqual(blocker.status, JourneyBlockerStatus.RESOLVED)
        self.assertEqual(step.status, JourneyStepStatus.IN_PROGRESS)
        self.assertEqual(sum(kind == "ok" for kind, _ in outcomes), 2)

    def test_review_double_decision_has_one_winner(self):
        assign_journey(journey=self.journey, profile=self.reviewer, responsibility=JourneyAssignmentResponsibility.REVIEWER, assigned_by=self.manager)
        artifact = create_artifact(journey=self.journey, uploaded_file=pdf_upload(b"review"), uploaded_by=self.beneficiary, kind=JourneyArtifactKind.CV, title="CV review")
        review = request_artifact_review(artifact=artifact, reviewer=self.reviewer, requested_by=self.manager)
        outcomes = run_pair(
            lambda: decide_artifact_review(review=JourneyArtifactReview.objects.get(pk=review.pk), actor=self.reviewer, decision=JourneyArtifactReviewStatus.APPROVED),
            lambda: decide_artifact_review(review=JourneyArtifactReview.objects.get(pk=review.pk), actor=self.reviewer, decision=JourneyArtifactReviewStatus.CHANGES_REQUESTED),
        )
        review.refresh_from_db(); artifact.refresh_from_db()
        self.assertIn(review.status, {JourneyArtifactReviewStatus.APPROVED, JourneyArtifactReviewStatus.CHANGES_REQUESTED})
        expected = JourneyArtifactStatus.ACCEPTED if review.status == JourneyArtifactReviewStatus.APPROVED else JourneyArtifactStatus.REJECTED
        self.assertEqual(artifact.status, expected)
        self.assertEqual(sum(kind == "ok" for kind, _ in outcomes), 1)

    def test_artifact_version_race_creates_one_successor(self):
        artifact = create_artifact(journey=self.journey, uploaded_file=pdf_upload(b"v1"), uploaded_by=self.beneficiary, kind=JourneyArtifactKind.CV, title="CV version race")
        outcomes = run_pair(
            lambda: create_artifact_version(artifact=type(artifact).objects.get(pk=artifact.pk), uploaded_file=pdf_upload(b"v2-a"), uploaded_by=self.beneficiary),
            lambda: create_artifact_version(artifact=type(artifact).objects.get(pk=artifact.pk), uploaded_file=pdf_upload(b"v2-b"), uploaded_by=self.beneficiary),
        )
        successors = type(artifact).objects.filter(supersedes=artifact)
        self.assertEqual(successors.count(), 1)
        self.assertEqual(successors.get().version, 2)
        self.assertEqual(sum(kind == "ok" for kind, _ in outcomes), 1)
