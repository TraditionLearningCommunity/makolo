from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from access.models import Access
from accounts.models import UserProfile
from activities.models import Activity, ActivityStatus, ActivityVisibility, Occurrence, OccurrenceStatus
from authorization.models import Mandate
from commerce.models import CommerceOrder
from journeys.models import Journey
from notifications.models import Notification
from opportunities.models import (
    Opportunity,
    OpportunityKind,
    OpportunityPublicationStatus,
    OpportunityRevision,
)
from payments.models import Payment

from .models import ShareDelivery, ShareIntent, ShareLink, ShareStatus
from .services import (
    accept_share_delivery,
    create_direct_activity_share,
    create_direct_opportunity_share,
    revoke_share_link,
)


User = get_user_model()


@override_settings(MAKOLO_PUBLIC_BASE_URL="https://makolo.example")
class SharingP2DirectTests(TestCase):
    password = "Strong-sharing-password-2026!"

    def setUp(self):
        self.sender = User.objects.create_user(
            username="p2-sender",
            email="p2-sender@makolo.test",
            password=self.password,
            first_name="Christophe",
        )
        self.recipient = User.objects.create_user(
            username="p2-recipient",
            email="p2-recipient@makolo.test",
            password=self.password,
            first_name="Gilbert",
        )
        self.other = User.objects.create_user(
            username="p2-other",
            email="p2-other@makolo.test",
            password=self.password,
            first_name="Patrick",
        )
        self.sender_profile = UserProfile.objects.create(user=self.sender, searchable=True)
        self.recipient_profile = UserProfile.objects.create(user=self.recipient, searchable=True)
        self.other_profile = UserProfile.objects.create(user=self.other, searchable=True)
        self.activity = Activity.objects.create(
            owner_profile=self.sender,
            created_by=self.sender,
            title="Formation Makolo P2",
            short_description="Contexte direct P2.",
            status=ActivityStatus.PUBLISHED,
            visibility=ActivityVisibility.PUBLIC,
        )
        start_at = timezone.now() + timedelta(days=10)
        self.occurrence = Occurrence.objects.create(
            activity=self.activity,
            label="Session exacte P2",
            start_at=start_at,
            end_at=start_at + timedelta(hours=2),
            timezone="Africa/Lubumbashi",
            status=OccurrenceStatus.SCHEDULED,
        )
        self.opportunity = Opportunity.objects.create(
            kind=OpportunityKind.SCHOLARSHIP,
            created_by=self.sender,
        )
        self.revision = OpportunityRevision.objects.create(
            opportunity=self.opportunity,
            version=1,
            title="Bourse Makolo P2",
            summary="Une opportunité directe P2.",
            issuer_name="Fondation Makolo",
            timezone="Africa/Lubumbashi",
            created_by=self.sender,
        )
        self.revision.published_at = timezone.now()
        self.revision._allow_publication = True
        self.revision.save(update_fields=["published_at"])
        self.opportunity.publication_status = OpportunityPublicationStatus.PUBLISHED
        self.opportunity.current_revision = self.revision
        self.opportunity.published_at = self.revision.published_at
        self.opportunity._allow_lifecycle_transition = True
        self.opportunity.save(
            update_fields=["publication_status", "current_revision", "published_at", "updated_at"]
        )
        self.opportunity.refresh_from_db()

    def direct(self, *, intent=ShareIntent.VIEW):
        return create_direct_activity_share(
            created_by=self.sender,
            recipient=self.recipient_profile,
            activity=self.activity,
            occurrence=self.occurrence,
            intent=intent,
        )

    def business_counts(self):
        return {
            "journeys": Journey.objects.count(),
            "orders": CommerceOrder.objects.count(),
            "payments": Payment.objects.count(),
            "accesses": Access.objects.count(),
            "mandates": Mandate.objects.count(),
        }

    def test_direct_share_uses_delivery_profile_and_not_external_link(self):
        created = self.direct()
        self.assertEqual(created.delivery.recipient, self.recipient_profile)
        self.assertEqual(created.delivery.envelope, created.envelope)
        self.assertFalse(ShareLink.objects.filter(envelope=created.envelope).exists())
        self.assertEqual(
            ShareDelivery.objects.filter(
                envelope=created.envelope,
                recipient=self.recipient_profile,
            ).count(),
            1,
        )

    def test_opportunity_direct_share_preserves_revision_and_has_no_external_link(self):
        created = create_direct_opportunity_share(
            created_by=self.sender,
            recipient=self.recipient_profile,
            opportunity_revision=self.revision,
            intent=ShareIntent.START_JOURNEY,
        )
        self.assertEqual(
            created.envelope.opportunity_subject.opportunity_revision_id,
            self.revision.pk,
        )
        self.assertEqual(created.delivery.recipient, self.recipient_profile)
        self.assertFalse(ShareLink.objects.filter(envelope=created.envelope).exists())

        self.client.force_login(self.recipient)
        response = self.client.get(
            reverse("sharing:delivery", kwargs={"delivery_id": created.delivery.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.revision.title)

    def test_self_share_and_inactive_recipient_are_rejected(self):
        with self.assertRaises(ValidationError):
            create_direct_activity_share(
                created_by=self.sender,
                recipient=self.sender_profile,
                activity=self.activity,
                occurrence=self.occurrence,
            )
        self.recipient.is_active = False
        self.recipient.save(update_fields=["is_active"])
        with self.assertRaises(ValidationError):
            self.direct()

    def test_notification_targets_only_recipient_and_uses_delivery_url(self):
        created = self.direct()
        notification = Notification.objects.get(metadata__share_delivery_id=str(created.delivery.pk))
        self.assertEqual(notification.recipient, self.recipient)
        self.assertNotEqual(notification.recipient, self.other)
        self.assertEqual(
            notification.action_url,
            reverse("sharing:delivery", kwargs={"delivery_id": created.delivery.pk}),
        )

    def test_only_recipient_can_open_and_anonymous_login_keeps_next(self):
        created = self.direct()
        url = reverse("sharing:delivery", kwargs={"delivery_id": created.delivery.pk})
        anonymous = self.client.get(url)
        self.assertEqual(anonymous.status_code, 302)
        self.assertIn("next=", anonymous.url)

        self.client.force_login(self.other)
        self.assertEqual(self.client.get(url).status_code, 403)

        self.client.force_login(self.recipient)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.activity.title)
        self.assertContains(response, self.occurrence.label)
        created.delivery.refresh_from_db()
        self.assertIsNotNone(created.delivery.opened_at)

    def test_visibility_is_rechecked_at_open(self):
        created = self.direct()
        self.activity.visibility = ActivityVisibility.PRIVATE
        self.activity.save(update_fields=["visibility", "updated_at"])
        self.client.force_login(self.recipient)
        response = self.client.get(
            reverse("sharing:delivery", kwargs={"delivery_id": created.delivery.pk})
        )
        self.assertEqual(response.status_code, 404)

    def test_accept_and_decline_are_post_only_mutually_exclusive_and_create_no_rights(self):
        accepted = self.direct(intent=ShareIntent.PARTICIPATE).delivery
        before = self.business_counts()
        self.client.force_login(self.recipient)
        accept_url = reverse("sharing:delivery-accept", kwargs={"delivery_id": accepted.pk})
        self.assertEqual(self.client.get(accept_url).status_code, 405)
        response = self.client.post(accept_url)
        self.assertEqual(response.status_code, 302)
        accepted.refresh_from_db()
        self.assertIsNotNone(accepted.accepted_at)
        self.assertIsNone(accepted.declined_at)
        self.assertEqual(self.business_counts(), before)

        declined = self.direct().delivery
        decline_url = reverse("sharing:delivery-decline", kwargs={"delivery_id": declined.pk})
        self.assertEqual(self.client.get(decline_url).status_code, 405)
        self.client.post(decline_url)
        declined.refresh_from_db()
        self.assertIsNotNone(declined.declined_at)
        self.assertIsNone(declined.accepted_at)
        self.assertEqual(self.business_counts(), before)
        with self.assertRaises(ValidationError):
            accept_share_delivery(delivery_id=declined.pk, user=self.recipient)

    def test_revoked_envelope_makes_delivery_unusable(self):
        created = self.direct()
        revoke_share_link(envelope=created.envelope, actor=self.sender)
        created.envelope.refresh_from_db()
        self.assertEqual(created.envelope.status, ShareStatus.REVOKED)
        self.client.force_login(self.recipient)
        response = self.client.get(
            reverse("sharing:delivery", kwargs={"delivery_id": created.delivery.pk})
        )
        self.assertEqual(response.status_code, 404)

    def test_profile_search_does_not_expose_email(self):
        self.client.force_login(self.sender)
        response = self.client.get(reverse("sharing:profile-search"), {"q": "Gil"})
        self.assertEqual(response.status_code, 200)
        payload = response.json()["results"]
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["id"], str(self.recipient_profile.pk))
        self.assertNotIn("email", payload[0])
