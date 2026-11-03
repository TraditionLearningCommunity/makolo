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
from .services import create_resource, publish_resource, replace_resource, retire_resource, resources_for_journey


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
        self.assertEqual(response["Cache-Control"], "private, no-store")

    def test_missing_public_file_returns_404_without_storage_error(self):
        upload = SimpleUploadedFile(
            "public.pdf", b"%PDF-1.4\n%%EOF\n", content_type="application/pdf"
        )
        resource = create_resource(
            activity=self.activity, actor=self.operator, key="missing-public",
            title="Public PDF", kind=ResourceKind.FILE,
            uploaded_file=upload, visibility=ResourceVisibility.PUBLIC,
        )
        publish_resource(resource=resource, actor=self.operator)
        url = reverse("preparation:resource-download", kwargs={"resource_id": resource.pk})
        resource.file.storage.delete(resource.file.name)
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_unpublished_activity_never_grants_anonymous_public_download(self):
        from activities.models import ActivityStatus, ActivityVisibility

        upload = SimpleUploadedFile(
            "private.pdf", b"%PDF-1.4\n%%EOF\n", content_type="application/pdf"
        )
        resource = create_resource(
            activity=self.activity, actor=self.operator, key="not-discoverable",
            title="Public-label only", kind=ResourceKind.FILE,
            uploaded_file=upload, visibility=ResourceVisibility.PUBLIC,
        )
        publish_resource(resource=resource, actor=self.operator)
        self.activity.status = ActivityStatus.DRAFT
        self.activity.visibility = ActivityVisibility.PRIVATE
        self.activity.save()
        url = reverse("preparation:resource-download", kwargs={"resource_id": resource.pk})
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_documentary_csv_is_signature_checked(self):
        csv_file = SimpleUploadedFile(
            "schedule.csv", b"date,place\\n2026-12-01,Lubumbashi\\n",
            content_type="text/csv",
        )
        resource = create_resource(
            activity=self.activity, actor=self.operator, key="public-csv",
            title="Planning CSV", kind=ResourceKind.FILE,
            uploaded_file=csv_file, visibility=ResourceVisibility.PUBLIC,
        )
        self.assertEqual(resource.mime_type, "text/csv")
        with self.assertRaises(ValidationError):
            create_resource(
                activity=self.activity, actor=self.operator, key="fake-mp4",
                title="Fausse video", kind=ResourceKind.FILE,
                uploaded_file=SimpleUploadedFile(
                    "movie.mp4", b"not-an-mp4", content_type="video/mp4"
                ),
            )

    def test_full_text_reader_uses_preparation_authorization(self):
        resource = create_resource(
            activity=self.activity,
            actor=self.operator,
            key="text-reader",
            title="Guide texte",
            kind=ResourceKind.TEXT,
            text_content="Instructions completes pour le parcours.",
            visibility=ResourceVisibility.PARTICIPANT,
        )
        publish_resource(resource=resource, actor=self.operator)
        url = reverse("preparation:resource-text", kwargs={"resource_id": resource.pk})
        self.assertEqual(self.client.get(url).status_code, 404)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.client.force_login(self.participant)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Instructions completes", response.content)
        self.assertEqual(response["Cache-Control"], "private, no-store")
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")

    def test_full_text_reader_never_exposes_file_or_url(self):
        resource = create_resource(
            activity=self.activity,
            actor=self.operator,
            key="external-reference",
            title="Site externe",
            kind=ResourceKind.URL,
            external_url="https://example.org/",
            visibility=ResourceVisibility.PUBLIC,
        )
        publish_resource(resource=resource, actor=self.operator)
        self.client.force_login(self.operator)
        url = reverse("preparation:resource-text", kwargs={"resource_id": resource.pk})
        self.assertEqual(self.client.get(url).status_code, 404)

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

    def test_resource_retirement_requires_authority_and_keeps_history(self):
        resource = create_resource(
            activity=self.activity, actor=self.operator, key="demo-retire",
            title="Document", kind=ResourceKind.TEXT, text_content="Example",
            visibility=ResourceVisibility.PUBLIC,
        )
        publish_resource(resource=resource, actor=self.operator)
        with self.assertRaises(PermissionDenied):
            retire_resource(resource=resource, actor=self.other)
        resource.refresh_from_db()
        self.assertEqual(resource.status, ResourceStatus.PUBLISHED)
        retired = retire_resource(resource=resource, actor=self.operator)
        self.assertEqual(retired.status, ResourceStatus.RETIRED)
        self.assertTrue(ActivityResource.objects.filter(pk=resource.pk).exists())
        with self.assertRaises(ValidationError):
            retire_resource(resource=retired, actor=self.operator)

    def test_csv_download_preserves_extension_and_is_attachment(self):
        resource = create_resource(
            activity=self.activity, actor=self.operator, key="schedule-csv",
            title="Calendrier", kind=ResourceKind.FILE,
            uploaded_file=SimpleUploadedFile(
                "schedule.csv", b"date,place\n2026-12-01,Kinshasa\n", content_type="text/csv"
            ), visibility=ResourceVisibility.PUBLIC,
        )
        publish_resource(resource=resource, actor=self.operator)
        url = reverse("preparation:resource-download", kwargs={"resource_id": resource.pk})
        self.client.force_login(self.operator)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv")
        self.assertIn(".csv", response["Content-Disposition"])
        self.assertTrue(response["Content-Disposition"].startswith("attachment;"))
        response.close()
