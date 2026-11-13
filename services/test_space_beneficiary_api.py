"""Applicant Space Service Journey + native private artifact integration tests."""
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from activities.models import Activity, ActivityStatus, ActivityVisibility
from authorization.constants import PermissionCode, SystemRoleCode
from authorization.services import can, grant_space_role, revoke_mandate
from groups.models import ActivityGroupEligibility, ActivityGroupEligibilityStatus, Group
from journeys.models import Journey, JourneyStatus
from organizations.models import Organization

from .models import ServiceDetails, ServiceKind, ServiceIntakeQuestion, ServiceIntakeQuestionType


User = get_user_model()


class ApplicantSpaceServiceAPITests(TestCase):
    def setUp(self):
        self.manager = User.objects.create_user(
            username="applicant-space-manager", email="applicant-mgr@example.test",
        )
        self.colleague = User.objects.create_user(
            username="applicant-space-colleague", email="applicant-col@example.test",
        )
        self.unmandated = User.objects.create_user(
            username="applicant-space-unmandated", email="applicant-out@example.test",
        )
        self.provider = User.objects.create_user(
            username="applicant-space-provider", email="provider@example.test",
        )
        self.space = Organization.objects.create(
            name="Institution demanderesse", created_by=self.manager,
        )
        self.other_space = Organization.objects.create(
            name="Autre institution", created_by=self.unmandated,
        )
        self.mandate = grant_space_role(
            profile=self.manager, space=self.space,
            role=SystemRoleCode.SPACE_OWNER,
        )
        self.colleague_mandate = grant_space_role(
            profile=self.colleague, space=self.space,
            role=SystemRoleCode.ACTIVITY_MANAGER,
        )
        self.activity = Activity.objects.create(
            owner_profile=self.provider, created_by=self.provider,
            title="Accompagnement professionnel",
            status=ActivityStatus.PUBLISHED,
            visibility=ActivityVisibility.PUBLIC,
        )
        self.service = ServiceDetails.objects.create(
            activity=self.activity, service_kind=ServiceKind.APPLICATION_SUPPORT,
        )
        self.question = ServiceIntakeQuestion.objects.create(
            service=self.service, key="goal",
            prompt="Quel accompagnement ?", is_required=True,
            question_type=ServiceIntakeQuestionType.SHORT_TEXT,
        )
        self.api = APIClient()
        self.key = "space-applicant-start-key-0001"
        self.start_url = reverse(
            "organizations_api:workspace-service-applicant-start",
            kwargs={"slug": self.space.slug, "pk": self.service.pk},
        )

    def login(self, user):
        self.api.force_authenticate(user=user)

    def start(self, *, objective="Représenter mon institution", key=None):
        return self.api.post(
            self.start_url, {"objective": objective},
            format="json", HTTP_IDEMPOTENCY_KEY=key or self.key,
        )

    def _journey_url(self, journey):
        return reverse(
            "organizations_api:workspace-beneficiary-journey",
            kwargs={"slug": self.space.slug, "journey_id": journey.pk},
        )

    def _artifacts_url(self, journey):
        return reverse(
            "organizations_api:workspace-beneficiary-artifacts",
            kwargs={"slug": self.space.slug, "journey_id": journey.pk},
        )

    def test_space_service_start_replay_and_isolated_personal_authority(self):
        self.login(self.manager)
        info = self.api.get(self.start_url)
        self.assertEqual(info.status_code, 200)
        self.assertEqual(info.data["beneficiary"]["id"], str(self.space.pk))
        first = self.start()
        self.assertEqual(first.status_code, 201)
        journey = Journey.objects.get(pk=first.data["journey"]["id"])
        self.assertEqual(journey.beneficiary_space_id, self.space.pk)
        self.assertIsNone(journey.beneficiary_id)
        self.assertIsNone(journey.external_beneficiary_id)
        self.assertEqual(journey.initiated_by, self.manager)
        self.assertEqual(self.start().status_code, 200)
        self.assertEqual(self.start(objective="Demande modifiée").status_code, 409)
        self.assertEqual(Journey.objects.filter(activity=self.activity).count(), 1)
        self.assertEqual(
            self.api.get(f"/api/v1/me/journeys/{journey.pk}/").status_code,
            404,
        )
        details = self.api.get(self._journey_url(journey))
        self.assertEqual(details.status_code, 200)
        self.assertEqual(
            details.data["data"]["identity"]["beneficiary"]["id"],
            str(self.space.pk),
        )
        self.assertFalse(
            can(
                self.manager, PermissionCode.ACTIVITY_SERVICES_CASES_MANAGE,
                activity=self.activity,
            )
        )

    def test_space_intake_submits_from_mandate_and_revocation_denies_new_access(self):
        self.login(self.manager)
        created = self.start()
        journey = Journey.objects.get(pk=created.data["journey"]["id"])
        intake = reverse(
            "organizations_api:workspace-beneficiary-intake",
            kwargs={"slug": self.space.slug, "journey_id": journey.pk},
        )
        self.assertEqual(self.api.get(intake).status_code, 200)
        result = self.api.post(
            intake, {"answers": {str(self.question.pk): "Examiner les dossiers"},
                     "submit": True}, format="json",
        )
        self.assertEqual(result.status_code, 200)
        journey.refresh_from_db()
        self.assertEqual(journey.status, JourneyStatus.CONFIRMED)
        self.login(self.colleague)
        self.assertEqual(self.api.get(self._journey_url(journey)).status_code, 200)
        revoke_mandate(mandate=self.colleague_mandate, actor=self.manager)
        self.assertEqual(self.api.get(self._journey_url(journey)).status_code, 404)
        self.assertEqual(self.api.get(intake).status_code, 404)

    def test_unknown_space_and_foreign_journey_never_disclose_data(self):
        self.login(self.unmandated)
        self.assertEqual(self.api.get(self.start_url).status_code, 404)
        self.assertEqual(self.start().status_code, 404)
        self.login(self.manager)
        created = self.start()
        journey = Journey.objects.get(pk=created.data["journey"]["id"])
        other_url = reverse(
            "organizations_api:workspace-beneficiary-journey",
            kwargs={"slug": self.other_space.slug, "journey_id": journey.pk},
        )
        self.assertEqual(self.api.get(other_url).status_code, 404)
        self.login(self.unmandated)
        self.assertEqual(self.api.get(self._journey_url(journey)).status_code, 404)

    def test_profile_group_gate_is_not_inherited_by_applicant_space(self):
        group = Group.objects.create(
            name="Admission par profil", owner_profile=self.provider,
            created_by=self.provider,
        )
        ActivityGroupEligibility.objects.create(
            group=group, activity=self.activity,
            status=ActivityGroupEligibilityStatus.APPROVED,
            requested_by=self.provider, decided_by=self.provider,
            decided_at=timezone.now(),
        )
        self.login(self.manager)
        self.assertEqual(self.api.get(self.start_url).status_code, 404)
        self.assertEqual(self.start().status_code, 404)
        self.assertFalse(Journey.objects.exists())

    def test_private_artifact_upload_replay_version_and_revocation(self):
        with TemporaryDirectory() as temporary_dir:
            with override_settings(MEDIA_ROOT=temporary_dir):
                self.login(self.manager)
                journey = Journey.objects.get(pk=self.start().data["journey"]["id"])
                url = self._artifacts_url(journey)

                def upload(content):
                    return self.api.post(
                        url, {
                            "title": "CV institutionnel",
                            "kind": "cv",
                            "sensitivity": "normal",
                            "file": SimpleUploadedFile(
                                "cv.txt", content, content_type="text/plain",
                            ),
                        }, format="multipart",
                    )

                first = upload(b"Mon CV")
                self.assertEqual(first.status_code, 201)
                artifact_id = first.data["id"]
                repeated = upload(b"Mon CV")
                self.assertEqual(repeated.status_code, 200)
                self.assertEqual(repeated.data["id"], artifact_id)
                self.assertEqual(upload(b"Autre document").status_code, 409)
                listing = self.api.get(url)
                self.assertEqual(listing.status_code, 200)
                self.assertEqual(len(listing.data["artifacts"]), 1)
                self.assertTrue(listing.data["artifacts"][0]["capabilities"]["download"])
                original = listing.data["artifacts"][0]["links"]["download"]
                self.assertEqual(self.api.get(original).status_code, 200)

                version_url = listing.data["artifacts"][0]["links"]["versions"]
                newer = self.api.post(
                    version_url, {
                        "sensitivity": "normal",
                        "file": SimpleUploadedFile(
                            "cv-v2.txt", b"Mon CV version 2",
                            content_type="text/plain",
                        ),
                    }, format="multipart",
                )
                self.assertEqual(newer.status_code, 201)
                self.assertEqual(newer.data["version"], 2)
                self.assertEqual(
                    len(self.api.get(url).data["artifacts"]), 2,
                )
                self.login(self.unmandated)
                self.assertEqual(self.api.get(url).status_code, 404)
                self.assertEqual(self.api.get(original).status_code, 404)

    def test_identity_document_upload_requires_restricted_space_authority(self):
        self.login(self.manager)
        journey = Journey.objects.get(pk=self.start().data["journey"]["id"])
        result = self.api.post(
            self._artifacts_url(journey),
            {
                "title": "Identité",
                "kind": "identity_document",
                "sensitivity": "normal",
                "file": SimpleUploadedFile(
                    "proof.txt", b"Document", content_type="text/plain",
                ),
            },
            format="multipart",
        )
        self.assertEqual(result.status_code, 400)
