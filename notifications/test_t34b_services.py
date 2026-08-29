from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from accounts.models import NotificationPreference
from activities.models import Activity
from authorization.constants import SystemRoleCode
from authorization.services import grant_activity_role, revoke_mandate
from core.models import DomainEventOutbox
from domain_events.contracts import DomainEventType
from journeys.collaboration_models import JourneyArtifactKind, JourneyArtifactSensitivity, JourneyAssignmentResponsibility
from journeys.collaboration_services import assign_journey, create_artifact, request_artifact_review
from notifications.models import DeliveryStatus, Notification, NotificationCategory, NotificationDelivery, NotificationKind
from notifications.services import create_notification
from organizations.models import Organization
from services.models import ServiceKind
from services.services import create_service_details, create_service_journey

from .services_domain_event_consumer import consume_services_opportunity_event


User = get_user_model()


def pdf_upload(text=b"private identity 123456"):
    return SimpleUploadedFile("identity.pdf", b"%PDF-1.4\n" + text + b"\n%%EOF", content_type="application/pdf")


class T34BNotificationTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="t34b-notif-owner", email="t34b-notif-owner@example.com", password="x")
        self.beneficiary = User.objects.create_user(username="t34b-notif-beneficiary", email="t34b-notif-beneficiary@example.com", password="x")
        self.manager = User.objects.create_user(username="t34b-notif-manager", email="t34b-notif-manager@example.com", password="x")
        self.reviewer = User.objects.create_user(username="t34b-notif-reviewer", email="t34b-notif-reviewer@example.com", password="x")
        self.space = Organization.objects.create(name="T34B notification space", created_by=self.owner)
        self.activity = Activity.objects.create(space=self.space, created_by=self.owner, title="T34B notifications")
        grant_activity_role(profile=self.manager, activity=self.activity, role=SystemRoleCode.ACTIVITY_SERVICE_MANAGER)
        self.reviewer_mandate = grant_activity_role(profile=self.reviewer, activity=self.activity, role=SystemRoleCode.ACTIVITY_SERVICE_REVIEWER)
        self.service = create_service_details(activity=self.activity, actor=self.manager, service_kind=ServiceKind.CAREER_SUPPORT)
        self.journey = create_service_journey(service=self.service, initiated_by=self.beneficiary, beneficiary=self.beneficiary)
        assign_journey(
            journey=self.journey,
            profile=self.reviewer,
            responsibility=JourneyAssignmentResponsibility.REVIEWER,
            assigned_by=self.manager,
        )

    def event(self, event_type, *, payload, source_type="test", source_id="1"):
        return DomainEventOutbox.objects.create(
            event_type=event_type,
            source_type=source_type,
            source_id=str(source_id),
            space_id=self.space.pk,
            activity_id=self.activity.pk,
            payload=payload,
            idempotency_key=f"t34b-notif:{event_type}:{source_id}:{DomainEventOutbox.objects.count()}",
        )

    def test_service_preference_skips_email_but_keeps_in_app_notification(self):
        preferences, _ = NotificationPreference.objects.get_or_create(user=self.beneficiary)
        preferences.service_notifications = False
        preferences.save(update_fields=["service_notifications", "updated_at"])
        notification = create_notification(
            recipient=self.beneficiary,
            kind=NotificationKind.SYSTEM,
            category=NotificationCategory.SERVICE,
            title="Service update",
            message="Safe update",
            dedup_key="t34b-pref-service",
        )
        self.assertTrue(Notification.objects.filter(pk=notification.pk).exists())
        delivery = notification.deliveries.get()
        self.assertEqual(delivery.status, DeliveryStatus.SKIPPED)

    def test_review_notification_is_deduplicated_and_does_not_copy_private_content(self):
        artifact = create_artifact(
            journey=self.journey,
            uploaded_file=pdf_upload(),
            uploaded_by=self.beneficiary,
            kind=JourneyArtifactKind.IDENTITY_DOCUMENT,
            title="Identity document",
            sensitivity=JourneyArtifactSensitivity.RESTRICTED,
        )
        review = request_artifact_review(
            artifact=artifact,
            reviewer=self.reviewer,
            requested_by=self.manager,
            comment="INTERNAL REVIEW SECRET 987654",
        )
        event = self.event(
            DomainEventType.JOURNEY_ARTIFACT_REVIEW_REQUESTED,
            payload={"journey_id": str(self.journey.pk), "review_id": str(review.pk), "artifact_id": str(artifact.pk)},
            source_type="journey_artifact_review",
            source_id=review.pk,
        )
        consume_services_opportunity_event(event)
        consume_services_opportunity_event(event)
        rows = Notification.objects.filter(domain_event=event, recipient=self.reviewer)
        self.assertEqual(rows.count(), 1)
        notification = rows.get()
        rendered = f"{notification.title} {notification.message} {notification.metadata}"
        self.assertNotIn("INTERNAL REVIEW SECRET", rendered)
        self.assertNotIn("987654", rendered)
        self.assertNotIn("identity.pdf", rendered)
        self.assertNotIn("private identity", rendered)

    def test_assignment_notification_revalidates_current_services_authority(self):
        assignment = self.journey.assignments.get(profile=self.reviewer)
        event = self.event(
            DomainEventType.JOURNEY_ASSIGNMENT_CREATED,
            payload={
                "journey_id": str(self.journey.pk),
                "assignment_id": str(assignment.pk),
                "profile_id": str(self.reviewer.pk),
                "responsibility": assignment.responsibility,
            },
            source_type="journey_assignment",
            source_id=assignment.pk,
        )
        revoke_mandate(mandate=self.reviewer_mandate)
        consume_services_opportunity_event(event)
        self.assertFalse(Notification.objects.filter(domain_event=event, recipient=self.reviewer).exists())

    def test_blocked_copy_never_exposes_blocker_description(self):
        step = self.journey.steps.create(title="Blocked step", status="blocked", created_by=self.manager)
        secret = "PRIVATE BLOCKER DESCRIPTION 424242"
        blocker = self.journey.blockers.create(title="Private blocker", description=secret, step=step, detected_by=self.manager)
        event = self.event(
            DomainEventType.JOURNEY_STEP_BLOCKED,
            payload={"journey_id": str(self.journey.pk), "step_id": str(step.pk), "blocker_id": str(blocker.pk)},
            source_type="journey_step",
            source_id=step.pk,
        )
        consume_services_opportunity_event(event)
        notification = Notification.objects.get(domain_event=event, recipient=self.beneficiary)
        self.assertNotIn(secret, notification.message)
        self.assertNotIn(secret, str(notification.metadata))
