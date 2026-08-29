from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from activities.models import Activity
from authorization.constants import SystemRoleCode
from authorization.services import grant_activity_role, grant_space_role, revoke_mandate
from journeys.collaboration_models import (
    JourneyArtifactKind,
    JourneyArtifactSensitivity,
    JourneyAssignment,
    JourneyAssignmentResponsibility,
)
from journeys.collaboration_services import (
    artifact_for_download,
    assign_journey,
    can_access_case,
    end_journey_assignment,
)
from organizations.models import Organization

from .models import IntakePolicy, OpportunityPolicy, ServiceKind
from .selectors import service_artifacts_visible_to, service_journeys_visible_to
from .services import create_service_details, create_service_journey


User = get_user_model()


def pdf_upload(text=b"private"):
    return SimpleUploadedFile(
        "document.pdf",
        b"%PDF-1.4\n" + text + b"\n%%EOF",
        content_type="application/pdf",
    )


class T34BServiceCaseAccessTests(TestCase):
    def setUp(self):
        self.bootstrap = User.objects.create_user(username="t34b-bootstrap", email="t34b-bootstrap@makolo.test", password="x")
        self.beneficiary = User.objects.create_user(username="t34b-beneficiary", email="t34b-beneficiary@makolo.test", password="x")
        self.manager = User.objects.create_user(username="t34b-manager", email="t34b-manager@makolo.test", password="x")
        self.facilitator = User.objects.create_user(username="t34b-facilitator", email="t34b-facilitator@makolo.test", password="x")
        self.reviewer = User.objects.create_user(username="t34b-reviewer", email="t34b-reviewer@makolo.test", password="x")
        self.space_admin = User.objects.create_user(username="t34b-space-admin", email="t34b-space-admin@makolo.test", password="x")
        self.outsider = User.objects.create_user(username="t34b-outsider", email="t34b-outsider@makolo.test", password="x")
        self.space = Organization.objects.create(name="T34B Services Space", created_by=self.bootstrap)
        self.activity = Activity.objects.create(
            created_by=self.bootstrap,
            space=self.space,
            title="T34B Service Activity",
        )
        grant_activity_role(profile=self.bootstrap, activity=self.activity)
        grant_space_role(profile=self.space_admin, space=self.space, role=SystemRoleCode.SPACE_ADMIN)
        grant_activity_role(profile=self.manager, activity=self.activity, role=SystemRoleCode.ACTIVITY_SERVICE_MANAGER)
        self.facilitator_mandate = grant_activity_role(
            profile=self.facilitator,
            activity=self.activity,
            role=SystemRoleCode.ACTIVITY_SERVICE_FACILITATOR,
        )
        grant_activity_role(profile=self.reviewer, activity=self.activity, role=SystemRoleCode.ACTIVITY_SERVICE_REVIEWER)
        self.service = create_service_details(
            activity=self.activity,
            actor=self.manager,
            service_kind=ServiceKind.CAREER_SUPPORT,
            opportunity_policy=OpportunityPolicy.NONE,
            intake_policy=IntakePolicy.AUTO_CONFIRM,
        )
        self.journey = create_service_journey(
            service=self.service,
            initiated_by=self.beneficiary,
            beneficiary=self.beneficiary,
            objective="Dossier privé T34B",
        )

    def test_manager_view_all_works_without_assignment(self):
        self.assertTrue(can_access_case(self.manager, self.journey))
        self.assertTrue(can_access_case(self.manager, self.journey, write=True))
        self.assertTrue(service_journeys_visible_to(self.manager).filter(pk=self.journey.pk).exists())

    def test_space_admin_activity_manager_assignment_and_same_space_are_not_service_authority(self):
        JourneyAssignment.objects.create(
            journey=self.journey,
            profile=self.bootstrap,
            responsibility=JourneyAssignmentResponsibility.SUPPORT,
            assigned_by=self.manager,
        )
        self.assertFalse(can_access_case(self.bootstrap, self.journey))
        self.assertFalse(can_access_case(self.space_admin, self.journey))
        self.assertFalse(can_access_case(self.outsider, self.journey))

    def test_facilitator_requires_both_mandate_and_active_assignment(self):
        self.assertFalse(can_access_case(self.facilitator, self.journey))
        assignment = assign_journey(
            journey=self.journey,
            profile=self.facilitator,
            responsibility=JourneyAssignmentResponsibility.FACILITATOR,
            assigned_by=self.manager,
        )
        self.assertTrue(can_access_case(self.facilitator, self.journey))
        end_journey_assignment(assignment=assignment, actor=self.manager)
        self.assertFalse(can_access_case(self.facilitator, self.journey))

    def test_revoked_mandate_removes_assignment_scoped_access(self):
        assign_journey(
            journey=self.journey,
            profile=self.facilitator,
            responsibility=JourneyAssignmentResponsibility.FACILITATOR,
            assigned_by=self.manager,
        )
        self.assertTrue(can_access_case(self.facilitator, self.journey))
        revoke_mandate(mandate=self.facilitator_mandate)
        self.assertFalse(can_access_case(self.facilitator, self.journey))
        self.assertFalse(service_journeys_visible_to(self.facilitator).filter(pk=self.journey.pk).exists())

    def test_restricted_artifact_is_denied_to_manager_but_allowed_to_reviewer_and_beneficiary(self):
        from journeys.collaboration_services import create_artifact

        restricted = create_artifact(
            journey=self.journey,
            uploaded_file=pdf_upload(b"identity-private"),
            uploaded_by=self.beneficiary,
            kind=JourneyArtifactKind.IDENTITY_DOCUMENT,
            title="Identity",
            sensitivity=JourneyArtifactSensitivity.RESTRICTED,
        )
        with self.assertRaises(PermissionDenied):
            artifact_for_download(actor=self.manager, artifact_id=restricted.pk)
        self.assertFalse(service_artifacts_visible_to(self.manager, journey=self.journey).filter(pk=restricted.pk).exists())

        assign_journey(
            journey=self.journey,
            profile=self.reviewer,
            responsibility=JourneyAssignmentResponsibility.REVIEWER,
            assigned_by=self.manager,
        )
        self.assertEqual(artifact_for_download(actor=self.reviewer, artifact_id=restricted.pk).pk, restricted.pk)
        self.assertTrue(service_artifacts_visible_to(self.reviewer, journey=self.journey).filter(pk=restricted.pk).exists())
        self.assertEqual(artifact_for_download(actor=self.beneficiary, artifact_id=restricted.pk).pk, restricted.pk)

    def test_manager_plus_reviewer_role_can_view_restricted_without_changing_manager_bundle(self):
        from journeys.collaboration_services import create_artifact

        restricted = create_artifact(
            journey=self.journey,
            uploaded_file=pdf_upload(b"combined-role"),
            uploaded_by=self.beneficiary,
            kind=JourneyArtifactKind.IDENTITY_DOCUMENT,
            title="Combined role",
            sensitivity=JourneyArtifactSensitivity.RESTRICTED,
        )
        with self.assertRaises(PermissionDenied):
            artifact_for_download(actor=self.manager, artifact_id=restricted.pk)
        grant_activity_role(profile=self.manager, activity=self.activity, role=SystemRoleCode.ACTIVITY_SERVICE_REVIEWER)
        self.assertEqual(artifact_for_download(actor=self.manager, artifact_id=restricted.pk).pk, restricted.pk)
