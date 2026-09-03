from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.utils import timezone

from access.models import Access, AccessUse, AccessUseResult
from activities.models import Activity, Occurrence
from authorization.constants import SystemRoleCode
from authorization.services import grant_activity_role
from journeys.models import ExternalBeneficiary

from .checkpoint_selectors import next_checkpoint, ordered_checkpoints
from .checkpoint_services import (
    assign_checkpoint_operator,
    close_checkpoint,
    observe_checkpoint,
    open_checkpoint,
    pause_checkpoint,
    resume_checkpoint,
)
from .models import CheckpointObservation, CheckpointStatus, OccurrenceCheckpoint


User = get_user_model()


class O2CheckpointTests(TestCase):
    def setUp(self):
        now = timezone.now()
        self.owner = User.objects.create_user(username="o2-owner", email="o2-owner@example.test", password="pw")
        self.manager = User.objects.create_user(username="o2-manager", email="o2-manager@example.test", password="pw")
        self.assigned_only = User.objects.create_user(username="o2-assigned", email="o2-assigned@example.test", password="pw")
        self.participant = User.objects.create_user(username="o2-participant", email="o2-participant@example.test", password="pw")
        self.other_participant = User.objects.create_user(username="o2-other", email="o2-other@example.test", password="pw")
        self.activity = Activity.objects.create(owner_profile=self.owner, created_by=self.owner, title="O2 Checkpoints")
        self.occurrence = Occurrence.objects.create(
            activity=self.activity,
            label="O2 Session",
            start_at=now + timedelta(days=1),
            end_at=now + timedelta(days=1, hours=2),
        )
        self.other_activity = Activity.objects.create(owner_profile=self.owner, created_by=self.owner, title="O2 Other")
        self.other_occurrence = Occurrence.objects.create(
            activity=self.other_activity,
            label="Other",
            start_at=now + timedelta(days=2),
            end_at=now + timedelta(days=2, hours=2),
        )
        grant_activity_role(
            profile=self.manager,
            activity=self.activity,
            role_code=SystemRoleCode.ACTIVITY_OPERATIONS_MANAGER,
            granted_by=self.owner,
            source="o2-test",
        )
        self.first = OccurrenceCheckpoint.objects.create(
            occurrence=self.occurrence, key="welcome", label="Accueil", position=1, required=True
        )
        self.optional = OccurrenceCheckpoint.objects.create(
            occurrence=self.occurrence, key="info", label="Information", position=2, required=False
        )
        self.second = OccurrenceCheckpoint.objects.create(
            occurrence=self.occurrence, key="boarding", label="Embarquement", position=3, required=True
        )
        self.external = ExternalBeneficiary.objects.create(
            display_name="Externe O2", email="external-o2@example.test", created_by=self.owner
        )

    def test_checkpoint_order_key_scope_and_default_status(self):
        self.assertEqual(list(ordered_checkpoints(occurrence=self.occurrence)), [self.first, self.optional, self.second])
        self.assertEqual(self.first.status, CheckpointStatus.PLANNED)
        with self.assertRaises(Exception):
            OccurrenceCheckpoint.objects.create(occurrence=self.occurrence, key="welcome", label="Duplicate")
        OccurrenceCheckpoint.objects.create(occurrence=self.other_occurrence, key="welcome", label="Allowed")

    def test_observation_requires_exactly_one_beneficiary_and_is_immutable(self):
        with self.assertRaises(ValidationError):
            CheckpointObservation(checkpoint=self.first, observed_by=self.manager).full_clean()
        with self.assertRaises(ValidationError):
            CheckpointObservation(
                checkpoint=self.first,
                profile=self.participant,
                external_beneficiary=self.external,
                observed_by=self.manager,
            ).full_clean()
        open_checkpoint(actor=self.manager, checkpoint=self.first)
        observation = observe_checkpoint(actor=self.manager, checkpoint=self.first, profile=self.participant)
        observation.source = "changed"
        with self.assertRaises(ValidationError):
            observation.save()

    def test_lifecycle_valid_transitions(self):
        self.assertEqual(open_checkpoint(actor=self.manager, checkpoint=self.first).status, CheckpointStatus.OPEN)
        self.assertEqual(pause_checkpoint(actor=self.manager, checkpoint=self.first).status, CheckpointStatus.PAUSED)
        self.assertEqual(resume_checkpoint(actor=self.manager, checkpoint=self.first).status, CheckpointStatus.OPEN)
        self.assertEqual(close_checkpoint(actor=self.manager, checkpoint=self.first).status, CheckpointStatus.CLOSED)
        with self.assertRaises(ValidationError):
            open_checkpoint(actor=self.manager, checkpoint=self.first)

    def test_assignment_does_not_grant_authority(self):
        assignment = assign_checkpoint_operator(actor=self.manager, checkpoint=self.first, profile=self.assigned_only)
        self.assertTrue(assignment.is_active)
        with self.assertRaises(PermissionDenied):
            open_checkpoint(actor=self.assigned_only, checkpoint=self.first)
        self.assertEqual(open_checkpoint(actor=self.manager, checkpoint=self.first).status, CheckpointStatus.OPEN)

    def test_flow_skips_optional_and_advances_after_observation(self):
        open_checkpoint(actor=self.manager, checkpoint=self.first)
        result = next_checkpoint(occurrence=self.occurrence, profile=self.participant)
        self.assertEqual(result.checkpoint, self.first)
        observe_checkpoint(actor=self.manager, checkpoint=self.first, profile=self.participant)
        result = next_checkpoint(occurrence=self.occurrence, profile=self.participant)
        self.assertEqual(result.checkpoint, self.second)
        self.assertEqual(result.blocked_reason, CheckpointStatus.PLANNED)
        open_checkpoint(actor=self.manager, checkpoint=self.second)
        result = next_checkpoint(occurrence=self.occurrence, profile=self.participant)
        self.assertEqual(result.checkpoint, self.second)
        observe_checkpoint(actor=self.manager, checkpoint=self.second, profile=self.participant)
        self.assertIsNone(next_checkpoint(occurrence=self.occurrence, profile=self.participant).checkpoint)

    def test_access_use_must_be_accepted_and_match_occurrence_and_beneficiary(self):
        open_checkpoint(actor=self.manager, checkpoint=self.first)
        access = Access.objects.create(
            beneficiary=self.participant,
            activity=self.activity,
            occurrence=self.occurrence,
            status="valid",
        )
        denied = AccessUse.objects.create(
            access=access,
            actor=self.manager,
            occurrence=self.occurrence,
            result=AccessUseResult.CANCELLED,
            source="o2-test",
        )
        with self.assertRaises(ValidationError):
            observe_checkpoint(
                actor=self.manager,
                checkpoint=self.first,
                profile=self.participant,
                access_use=denied,
            )
        accepted = AccessUse.objects.create(
            access=access,
            actor=self.manager,
            occurrence=self.occurrence,
            result=AccessUseResult.ACCEPTED,
            source="o2-test",
        )
        observation = observe_checkpoint(
            actor=self.manager,
            checkpoint=self.first,
            profile=self.participant,
            access_use=accepted,
            source="scanner",
            client_reference="retry-1",
        )
        retry = observe_checkpoint(
            actor=self.manager,
            checkpoint=self.first,
            profile=self.participant,
            access_use=accepted,
            source="scanner",
            client_reference="retry-1",
        )
        self.assertEqual(observation.pk, retry.pk)

    def test_access_use_cross_occurrence_and_wrong_beneficiary_are_rejected(self):
        open_checkpoint(actor=self.manager, checkpoint=self.first)
        other_access = Access.objects.create(
            beneficiary=self.participant,
            activity=self.other_activity,
            occurrence=self.other_occurrence,
            status="valid",
        )
        other_use = AccessUse.objects.create(
            access=other_access,
            actor=self.manager,
            occurrence=self.other_occurrence,
            result=AccessUseResult.ACCEPTED,
        )
        with self.assertRaises(ValidationError):
            observe_checkpoint(actor=self.manager, checkpoint=self.first, profile=self.participant, access_use=other_use)

        wrong_access = Access.objects.create(
            beneficiary=self.other_participant,
            activity=self.activity,
            occurrence=self.occurrence,
            status="valid",
        )
        wrong_use = AccessUse.objects.create(
            access=wrong_access,
            actor=self.manager,
            occurrence=self.occurrence,
            result=AccessUseResult.ACCEPTED,
        )
        with self.assertRaises(ValidationError):
            observe_checkpoint(actor=self.manager, checkpoint=self.first, profile=self.participant, access_use=wrong_use)

    def test_external_beneficiary_observation(self):
        open_checkpoint(actor=self.manager, checkpoint=self.first)
        observation = observe_checkpoint(
            actor=self.manager,
            checkpoint=self.first,
            external_beneficiary=self.external,
        )
        self.assertEqual(observation.external_beneficiary, self.external)
        self.assertIsNone(observation.profile)
