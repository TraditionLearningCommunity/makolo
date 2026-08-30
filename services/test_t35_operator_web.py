from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from activities.models import Activity
from authorization.constants import SystemRoleCode
from authorization.services import grant_activity_role, grant_space_role
from journeys.collaboration_models import JourneyArtifactKind, JourneyArtifactSensitivity, JourneyAssignmentResponsibility
from journeys.collaboration_services import assign_journey, create_artifact, request_artifact_review
from organizations.models import Organization

from .models import IntakePolicy, OpportunityPolicy, ServiceKind
from .services import create_service_details, create_service_journey


User = get_user_model()


def pdf_upload(name="document.pdf", content=b"operator-test"):
    return SimpleUploadedFile(name, b"%PDF-1.4\n" + content + b"\n%%EOF", content_type="application/pdf")


class T35OperatorWebTests(TestCase):
    def setUp(self):
        self.bootstrap = User.objects.create_user(username="t35op-bootstrap", email="t35op-bootstrap@makolo.test", password="x")
        self.beneficiary = User.objects.create_user(username="t35op-beneficiary", email="t35op-beneficiary@makolo.test", password="x")
        self.manager = User.objects.create_user(username="t35op-manager", email="t35op-manager@makolo.test", password="x")
        self.facilitator = User.objects.create_user(username="t35op-facilitator", email="t35op-facilitator@makolo.test", password="x")
        self.reviewer = User.objects.create_user(username="t35op-reviewer", email="t35op-reviewer@makolo.test", password="x")
        self.space_admin = User.objects.create_user(username="t35op-space-admin", email="t35op-space-admin@makolo.test", password="x")
        self.outsider = User.objects.create_user(username="t35op-outsider", email="t35op-outsider@makolo.test", password="x")
        self.space = Organization.objects.create(name="T35 Operator Space", created_by=self.bootstrap)
        self.activity = Activity.objects.create(created_by=self.bootstrap, space=self.space, title="Accompagnement T35")
        grant_activity_role(profile=self.bootstrap, activity=self.activity)
        grant_activity_role(profile=self.manager, activity=self.activity, role=SystemRoleCode.ACTIVITY_SERVICE_MANAGER)
        grant_activity_role(profile=self.facilitator, activity=self.activity, role=SystemRoleCode.ACTIVITY_SERVICE_FACILITATOR)
        grant_activity_role(profile=self.reviewer, activity=self.activity, role=SystemRoleCode.ACTIVITY_SERVICE_REVIEWER)
        grant_space_role(profile=self.space_admin, space=self.space, role=SystemRoleCode.SPACE_ADMIN)
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
            objective="Préparer mon dossier professionnel",
        )
        assign_journey(
            journey=self.journey,
            profile=self.facilitator,
            responsibility=JourneyAssignmentResponsibility.FACILITATOR,
            assigned_by=self.manager,
        )

    def test_manager_and_facilitator_only_see_authorized_operator_cases(self):
        self.client.force_login(self.manager)
        response = self.client.get(reverse("services:operator-dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Préparer mon dossier professionnel")
        self.assertEqual(self.client.get(reverse("services:operator-case", args=[self.journey.pk])).status_code, 200)

        self.client.force_login(self.facilitator)
        self.assertEqual(self.client.get(reverse("services:operator-case", args=[self.journey.pk])).status_code, 200)

        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(reverse("services:operator-case", args=[self.journey.pk])).status_code, 404)

    def test_space_services_console_requires_services_authority_not_space_admin(self):
        self.client.force_login(self.manager)
        response = self.client.get(reverse("organizations:console-services", kwargs={"slug": self.space.slug}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.activity.title)
        self.assertContains(response, "Préparer mon dossier professionnel")

        self.client.force_login(self.space_admin)
        response = self.client.get(reverse("organizations:console-services", kwargs={"slug": self.space.slug}))
        self.assertEqual(response.status_code, 403)

    def test_reviewer_queue_can_process_assigned_restricted_document(self):
        artifact = create_artifact(
            journey=self.journey,
            uploaded_file=pdf_upload("identity.pdf", b"restricted"),
            uploaded_by=self.beneficiary,
            kind=JourneyArtifactKind.IDENTITY_DOCUMENT,
            title="Pièce confidentielle",
            sensitivity=JourneyArtifactSensitivity.RESTRICTED,
        )
        assign_journey(
            journey=self.journey,
            profile=self.reviewer,
            responsibility=JourneyAssignmentResponsibility.REVIEWER,
            assigned_by=self.manager,
        )
        review = request_artifact_review(artifact=artifact, reviewer=self.reviewer, requested_by=self.manager)

        self.client.force_login(self.reviewer)
        response = self.client.get(reverse("services:reviewer-queue"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Pièce confidentielle")
        response = self.client.post(
            reverse("services:operator-review-decision", args=[review.pk]),
            {"decision": "approved", "comment": "Document conforme"},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        review.refresh_from_db()
        self.assertEqual(review.status, "approved")

    def test_facilitator_cannot_download_restricted_artifact_but_reviewer_can(self):
        artifact = create_artifact(
            journey=self.journey,
            uploaded_file=pdf_upload("private.pdf", b"restricted-download"),
            uploaded_by=self.beneficiary,
            kind=JourneyArtifactKind.IDENTITY_DOCUMENT,
            title="Document restreint",
            sensitivity=JourneyArtifactSensitivity.RESTRICTED,
        )
        self.client.force_login(self.facilitator)
        self.assertEqual(self.client.get(reverse("services:operator-artifact-download", args=[artifact.pk])).status_code, 404)

        assign_journey(
            journey=self.journey,
            profile=self.reviewer,
            responsibility=JourneyAssignmentResponsibility.REVIEWER,
            assigned_by=self.manager,
        )
        self.client.force_login(self.reviewer)
        response = self.client.get(reverse("services:operator-artifact-download", args=[artifact.pk]))
        self.assertEqual(response.status_code, 200)

    def test_manager_configuration_surface_updates_service_without_new_model(self):
        self.client.force_login(self.manager)
        url = reverse("services:operator-service-config", args=[self.service.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        response = self.client.post(
            url,
            {
                "action": "update-service",
                "service_kind": ServiceKind.DOCUMENT_SUPPORT,
                "opportunity_policy": OpportunityPolicy.OPTIONAL,
                "intake_policy": IntakePolicy.REVIEW_REQUIRED,
                "allows_external_beneficiary": "on",
                "completion_policy": "required_steps",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.service.refresh_from_db()
        self.assertEqual(self.service.service_kind, ServiceKind.DOCUMENT_SUPPORT)
        self.assertEqual(self.service.opportunity_policy, OpportunityPolicy.OPTIONAL)
        self.assertTrue(self.service.allows_external_beneficiary)

    def test_outsider_cannot_open_manager_configuration(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse("services:operator-service-config", args=[self.service.pk]))
        self.assertEqual(response.status_code, 403)
