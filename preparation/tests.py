from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from activities.models import Occurrence
from activities.services import create_activity
from journeys.models import Journey, JourneyStatus, WorkflowKind

from .models import ActivityResource, ResourceKind, ResourceStatus, ResourceVisibility
from .services import create_resource, publish_resource, replace_resource, resources_for_journey


User = get_user_model()


class PreparationResourceM2Tests(TestCase):
    def setUp(self):
        self.operator = User.objects.create_user(username="resource-operator", email="resource-operator@example.test", password="StrongPass2026!")
        self.participant = User.objects.create_user(username="resource-participant", email="resource-participant@example.test", password="StrongPass2026!")
        self.other = User.objects.create_user(username="resource-other", email="resource-other@example.test", password="StrongPass2026!")
        self.activity = create_activity(owner_profile=self.operator, created_by=self.operator, title="Voyage préparation")
        self.occurrence = Occurrence.objects.create(activity=self.activity, label="Départ", start_at=timezone.now() + timedelta(days=4))
        self.journey = Journey.objects.create(
            initiated_by=self.participant,
            beneficiary=self.participant,
            activity=self.activity,
            occurrence=self.occurrence,
            workflow=WorkflowKind.RESERVATION,
            status=JourneyStatus.CONFIRMED,
        )

    def test_participant_sees_public_and_participant_but_not_restricted(self):
        for key, visibility in (("public", ResourceVisibility.PUBLIC), ("participant", ResourceVisibility.PARTICIPANT), ("restricted", ResourceVisibility.RESTRICTED)):
            resource = create_resource(
                activity=self.activity,
                actor=self.operator,
                key=key,
                title=key.title(),
                kind=ResourceKind.TEXT,
                text_content="Instructions",
                visibility=visibility,
            )
            publish_resource(resource=resource, actor=self.operator)
        visible = resources_for_journey(journey=self.journey, actor=self.participant)
        self.assertEqual({item.key for item in visible}, {"public", "participant"})
        manager_visible = resources_for_journey(journey=self.journey, actor=self.operator)
        self.assertEqual({item.key for item in manager_visible}, {"public", "participant", "restricted"})
        with self.assertRaises(PermissionDenied):
            resources_for_journey(journey=self.journey, actor=self.other)

    def test_occurrence_resource_is_not_exposed_to_other_occurrence(self):
        resource = create_resource(
            activity=self.activity,
            occurrence=self.occurrence,
            actor=self.operator,
            key="boarding",
            title="Embarquement",
            kind=ResourceKind.TEXT,
            text_content="Présentez-vous 30 minutes avant.",
        )
        publish_resource(resource=resource, actor=self.operator)
        other_occurrence = Occurrence.objects.create(activity=self.activity, label="Autre départ", start_at=timezone.now() + timedelta(days=6))
        other_journey = Journey.objects.create(
            initiated_by=self.participant,
            beneficiary=self.participant,
            activity=self.activity,
            occurrence=other_occurrence,
            workflow=WorkflowKind.RESERVATION,
            status=JourneyStatus.CONFIRMED,
        )
        self.assertFalse(resources_for_journey(journey=other_journey, actor=self.participant))

    def test_replacement_preserves_provenance_and_supersedes_previous(self):
        resource = create_resource(
            activity=self.activity,
            actor=self.operator,
            key="guide",
            title="Guide",
            kind=ResourceKind.TEXT,
            text_content="Version 1",
        )
        publish_resource(resource=resource, actor=self.operator)
        replacement = replace_resource(resource=resource, actor=self.operator, text_content="Version 2", significant_update=True)
        resource.refresh_from_db()
        self.assertEqual(resource.status, ResourceStatus.SUPERSEDED)
        self.assertEqual(replacement.status, ResourceStatus.PUBLISHED)
        self.assertEqual(replacement.version, 2)
        self.assertEqual(replacement.supersedes_id, resource.pk)

    def test_file_resource_uses_private_storage_and_authorized_download(self):
        upload = SimpleUploadedFile("guide.pdf", b"%PDF-1.4\n%%EOF\n", content_type="application/pdf")
        resource = create_resource(
            activity=self.activity,
            actor=self.operator,
            key="guide-pdf",
            title="Guide PDF",
            kind=ResourceKind.FILE,
            uploaded_file=upload,
            visibility=ResourceVisibility.PARTICIPANT,
        )
        publish_resource(resource=resource, actor=self.operator)
        with self.assertRaises(ValueError):
            resource.file.storage.url(resource.file.name)
        url = reverse("preparation:resource-download", kwargs={"resource_id": resource.pk})
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.client.force_login(self.participant)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")

    def test_invalid_file_signature_is_rejected(self):
        upload = SimpleUploadedFile("fake.pdf", b"not-a-pdf", content_type="application/pdf")
        with self.assertRaises(ValidationError):
            create_resource(
                activity=self.activity,
                actor=self.operator,
                key="fake",
                title="Faux PDF",
                kind=ResourceKind.FILE,
                uploaded_file=upload,
            )
        self.assertFalse(ActivityResource.objects.filter(key="fake").exists())
