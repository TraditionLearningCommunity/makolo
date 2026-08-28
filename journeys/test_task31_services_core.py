from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import TestCase

from activities.models import Activity
from authorization.services import grant_activity_role
from domain_events.models import DomainEventOutbox

from .collaboration_models import JourneyArtifactKind, JourneyArtifactReviewStatus, JourneyArtifactSensitivity, JourneyArtifactStatus, JourneyAssignment, JourneyAssignmentResponsibility, JourneyAssignmentStatus, JourneyBlockerStatus, JourneyNoteVisibility, JourneyStepKind, JourneyStepStatus
from .collaboration_services import add_step_dependency, artifact_for_download, assign_journey, can_access_case, complete_step, create_artifact, create_artifact_version, create_blocker, create_note, create_step, decide_artifact_review, mark_ready, notes_for_actor, request_artifact_review, resolve_blocker, skip_step, start_step
from .models import JourneyStatus, WorkflowKind
from .services import _fulfill_service_journey, confirm_journey, create_journey, fulfill_journey, start_journey, submit_journey


User = get_user_model()


def pdf_upload(name="cv.pdf", text=b"Makolo CV"):
    return SimpleUploadedFile(name, b"%PDF-1.4\n" + text + b"\n%%EOF", content_type="application/pdf")


class Task31JourneyCoreTests(TestCase):
    def setUp(self):
        self.manager = User.objects.create_user(username="t31-manager", email="t31-manager@example.com", password="x")
        self.beneficiary = User.objects.create_user(username="t31-beneficiary", email="t31-beneficiary@example.com", password="x")
        self.reviewer = User.objects.create_user(username="t31-reviewer", email="t31-reviewer@example.com", password="x")
        self.outsider = User.objects.create_user(username="t31-outsider", email="t31-outsider@example.com", password="x")
        self.activity = Activity.objects.create(owner_profile=self.manager, created_by=self.manager, title="Aide CV T31")
        grant_activity_role(profile=self.manager, activity=self.activity)
        grant_activity_role(profile=self.reviewer, activity=self.activity)
        self.journey = create_journey(initiated_by=self.beneficiary, beneficiary=self.beneficiary, activity=self.activity, workflow=WorkflowKind.SERVICE)
        self.lead = assign_journey(journey=self.journey, profile=self.manager, responsibility=JourneyAssignmentResponsibility.LEAD, is_primary=True, assigned_by=self.manager)

    def test_service_journey_long_running_transition_and_event(self):
        submit_journey(journey=self.journey, actor=self.beneficiary)
        confirm_journey(journey=self.journey, actor=self.beneficiary)
        journey = start_journey(journey=self.journey, actor=self.manager)
        self.assertEqual(journey.status, JourneyStatus.IN_PROGRESS)
        self.assertIsNotNone(journey.started_at)
        self.assertTrue(DomainEventOutbox.objects.filter(source_type="journey", source_id=str(journey.pk), event_type="journey.in_progress").exists())
        with self.assertRaises(ValidationError):
            fulfill_journey(journey=journey, actor=self.manager)
        fulfilled = _fulfill_service_journey(journey=journey, actor=self.manager)
        self.assertEqual(fulfilled.status, JourneyStatus.FULFILLED)

    def test_historical_workflow_still_fulfills_from_confirmed(self):
        legacy = create_journey(initiated_by=self.beneficiary, beneficiary=self.beneficiary, activity=self.activity, workflow=WorkflowKind.REGISTRATION)
        submit_journey(journey=legacy, actor=self.beneficiary)
        confirm_journey(journey=legacy)
        fulfilled = fulfill_journey(journey=legacy)
        self.assertEqual(fulfilled.status, JourneyStatus.FULFILLED)
        self.assertIsNone(fulfilled.started_at)

    def test_dependencies_readiness_cycles_and_blockers(self):
        prerequisite = create_step(journey=self.journey, title="Collecter les informations", created_by=self.manager)
        dependant = create_step(journey=self.journey, title="Rédiger le CV", created_by=self.manager)
        add_step_dependency(step=dependant, depends_on=prerequisite, actor=self.manager)
        with self.assertRaises(ValidationError):
            add_step_dependency(step=prerequisite, depends_on=dependant, actor=self.manager)
        mark_ready(step=prerequisite, actor=self.manager)
        start_step(step=prerequisite, actor=self.manager)
        complete_step(step=prerequisite, actor=self.manager)
        dependant.refresh_from_db()
        self.assertEqual(dependant.status, JourneyStepStatus.READY)
        start_step(step=dependant, actor=self.manager)
        blocker = create_blocker(journey=self.journey, step=dependant, title="Pièce manquante", actor=self.manager)
        dependant.refresh_from_db()
        self.assertEqual(dependant.status, JourneyStepStatus.BLOCKED)
        with self.assertRaises(ValidationError):
            complete_step(step=dependant, actor=self.manager)
        resolve_blocker(blocker=blocker, actor=self.manager, resolution_note="Reçue")
        blocker.refresh_from_db(); dependant.refresh_from_db()
        self.assertEqual(blocker.status, JourneyBlockerStatus.RESOLVED)
        self.assertEqual(dependant.status, JourneyStepStatus.IN_PROGRESS)

    def test_required_skip_is_explicit_and_audited(self):
        step = create_step(journey=self.journey, title="Étape requise", created_by=self.manager, is_required=True)
        mark_ready(step=step, actor=self.manager)
        with self.assertRaises(ValidationError):
            skip_step(step=step, actor=self.manager, reason="Pas nécessaire")
        skipped = skip_step(step=step, actor=self.manager, reason="Décision métier documentée", allow_required=True)
        self.assertEqual(skipped.status, JourneyStepStatus.SKIPPED)
        self.assertEqual(skipped.status_changed_by, self.manager)
        self.assertTrue(skipped.status_reason)
        self.assertIsNotNone(skipped.skipped_at)

    def test_assignment_is_operational_not_authority_and_primary_lead_is_unique(self):
        outsider_assignment = assign_journey(journey=self.journey, profile=self.outsider, responsibility=JourneyAssignmentResponsibility.SUPPORT, assigned_by=self.manager)
        self.assertEqual(outsider_assignment.status, JourneyAssignmentStatus.ACTIVE)
        self.assertFalse(can_access_case(self.outsider, self.journey, write=True))
        with self.assertRaises(PermissionDenied):
            create_step(journey=self.journey, title="Tentative IDOR", created_by=self.outsider)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                JourneyAssignment.objects.create(journey=self.journey, profile=self.reviewer, responsibility=JourneyAssignmentResponsibility.LEAD, is_primary=True, assigned_by=self.manager)

    def test_artifact_version_review_private_boundary_and_notes(self):
        assign_journey(journey=self.journey, profile=self.reviewer, responsibility=JourneyAssignmentResponsibility.REVIEWER, assigned_by=self.manager)
        step = create_step(journey=self.journey, title="CV validé", kind=JourneyStepKind.DOCUMENT, created_by=self.manager)
        mark_ready(step=step, actor=self.manager); start_step(step=step, actor=self.manager)
        v1 = create_artifact(journey=self.journey, step=step, uploaded_file=pdf_upload(text=b"version one"), uploaded_by=self.beneficiary, kind=JourneyArtifactKind.CV, title="CV", sensitivity=JourneyArtifactSensitivity.SENSITIVE)
        self.assertEqual(v1.version, 1); self.assertEqual(len(v1.content_hash), 64)
        with self.assertRaises(ValueError):
            _ = v1.file.url
        review1 = request_artifact_review(artifact=v1, reviewer=self.reviewer, requested_by=self.manager)
        decide_artifact_review(review=review1, actor=self.reviewer, decision=JourneyArtifactReviewStatus.CHANGES_REQUESTED, comment="Renforcer les résultats")
        v1.refresh_from_db(); self.assertEqual(v1.status, JourneyArtifactStatus.REJECTED)
        v2 = create_artifact_version(artifact=v1, uploaded_file=pdf_upload(text=b"version two"), uploaded_by=self.beneficiary)
        v1.refresh_from_db(); self.assertEqual(v1.status, JourneyArtifactStatus.SUPERSEDED); self.assertEqual(v2.version, 2); self.assertEqual(v2.supersedes_id, v1.pk)
        review2 = request_artifact_review(artifact=v2, reviewer=self.reviewer, requested_by=self.manager)
        decide_artifact_review(review=review2, actor=self.reviewer, decision=JourneyArtifactReviewStatus.APPROVED)
        v2.refresh_from_db(); self.assertEqual(v2.status, JourneyArtifactStatus.ACCEPTED)
        complete_step(step=step, actor=self.manager)
        visible = create_note(journey=self.journey, author=self.beneficiary, body="Merci", visibility=JourneyNoteVisibility.BENEFICIARY_VISIBLE)
        internal = create_note(journey=self.journey, author=self.manager, body="Suivi interne", visibility=JourneyNoteVisibility.INTERNAL)
        beneficiary_ids = set(notes_for_actor(actor=self.beneficiary, journey=self.journey).values_list("pk", flat=True))
        self.assertIn(visible.pk, beneficiary_ids); self.assertNotIn(internal.pk, beneficiary_ids)
        with self.assertRaises(PermissionDenied):
            artifact_for_download(actor=self.outsider, artifact_id=v2.pk)
        self.assertEqual(artifact_for_download(actor=self.beneficiary, artifact_id=v2.pk).pk, v2.pk)
