from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from activities.models import Activity
from authorization.constants import SystemRoleCode
from authorization.services import grant_activity_role
from journeys.collaboration_models import (
    JourneyArtifactKind,
    JourneyAssignment,
    JourneyAssignmentResponsibility,
)
from journeys.collaboration_services import create_artifact
from journeys.models import WorkflowKind
from journeys.services import create_journey

from .action_memory import (
    ActionMemoryProvenanceCode,
    action_memory_for_journey,
)
from .models import PersonalAssetUse
from .services import create_personal_asset, create_personal_asset_version


User = get_user_model()


def pdf_upload(text=b"q3-private-provenance"):
    return SimpleUploadedFile(
        "document.pdf",
        b"%PDF-1.4\n" + text + b"\n%%EOF",
        content_type="application/pdf",
    )


class ActionMemoryProvenancePrivacyTests(TestCase):
    def setUp(self):
        self.actor = User.objects.create_user(
            username="q3-provenance-actor",
            email="q3-provenance-actor@example.test",
            password="x",
        )
        self.subject = User.objects.create_user(
            username="q3-provenance-subject",
            email="q3-provenance-subject@example.test",
            password="x",
        )
        self.operator = User.objects.create_user(
            username="q3-provenance-operator",
            email="q3-provenance-operator@example.test",
            password="x",
        )
        self.activity = Activity.objects.create(
            owner_profile=self.operator,
            created_by=self.operator,
            title="Q3 private provenance",
        )
        grant_activity_role(
            profile=self.actor,
            activity=self.activity,
            role=SystemRoleCode.ACTIVITY_SERVICE_FACILITATOR,
        )
        self.current = create_journey(
            initiated_by=self.subject,
            beneficiary=self.subject,
            activity=self.activity,
            workflow=WorkflowKind.SERVICE,
        )
        self.old = create_journey(
            initiated_by=self.subject,
            beneficiary=self.subject,
            activity=self.activity,
            workflow=WorkflowKind.SERVICE,
        )
        for journey, responsibility in (
            (self.current, JourneyAssignmentResponsibility.FACILITATOR),
            (self.old, JourneyAssignmentResponsibility.REVIEWER),
        ):
            JourneyAssignment.objects.create(
                journey=journey,
                profile=self.actor,
                responsibility=responsibility,
                assigned_by=self.operator,
            )

    def test_accessible_artifact_does_not_reveal_another_controllers_library_source(self):
        asset = create_personal_asset(
            controller=self.subject,
            subject_profile=self.subject,
            title="Source privée",
            kind=JourneyArtifactKind.CV,
        )
        version = create_personal_asset_version(
            actor=self.subject,
            asset=asset,
            uploaded_file=pdf_upload(),
        )
        artifact = create_artifact(
            journey=self.old,
            uploaded_file=pdf_upload(),
            uploaded_by=self.subject,
            kind=JourneyArtifactKind.CV,
            title="Artifact issu de la bibliothèque privée",
        )
        PersonalAssetUse.objects.create(
            asset_version=version,
            journey_artifact=artifact,
            used_by=self.subject,
        )

        candidate = next(
            item
            for item in action_memory_for_journey(actor=self.actor, journey=self.current)
            if item.source_id == str(artifact.pk)
        )

        self.assertEqual(candidate.provenance.code, ActionMemoryProvenanceCode.JOURNEY)
        self.assertIsNone(candidate.provenance.related_source_id)
