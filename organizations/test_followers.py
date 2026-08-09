from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from crm.models import CRMContact, MarketingConsent
from events.models import Event, EventStatus, EventVisibility
from notifications.models import Notification, NotificationDelivery

from .models import Organization, OrganizationFollow
from .services import follow_organization, unfollow_organization, update_follow_preferences


User = get_user_model()


class OrganizationFollowerTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="follow-owner",
            email="follow-owner@example.com",
            password="Strong-password-2026!",
        )
        self.follower = User.objects.create_user(
            username="follower",
            email="follower@example.com",
            password="Strong-password-2026!",
            first_name="Amina",
        )
        self.organization = Organization.objects.create(
            name="Makolo Culture",
            created_by=self.owner,
            public_profile=True,
        )
        self.other = Organization.objects.create(
            name="Makolo Sport",
            created_by=self.owner,
            public_profile=True,
        )

    def _follow(self, organization=None, **preferences):
        with self.captureOnCommitCallbacks(execute=True):
            return follow_organization(
                user=self.follower,
                organization=organization or self.organization,
                **preferences,
            )

    def test_follow_does_not_implicitly_opt_in_to_organizer_email(self):
        follow = self._follow()
        contact = CRMContact.objects.get(organization=self.organization, user=self.follower)
        self.assertTrue(follow.notify_new_events)
        self.assertFalse(follow.email_new_events)
        self.assertFalse(follow.email_announcements)
        self.assertEqual(contact.marketing_consent, MarketingConsent.UNKNOWN)

    def test_explicit_organizer_email_preference_creates_local_consent(self):
        follow = self._follow(email_announcements=True)
        contact = CRMContact.objects.get(organization=self.organization, user=self.follower)
        self.assertTrue(follow.email_announcements)
        self.assertEqual(contact.marketing_consent, MarketingConsent.SUBSCRIBED)
        self.assertEqual(contact.consent_source, "organization_follow_preferences")

    def test_preferences_are_isolated_per_organization(self):
        first = self._follow(email_announcements=True)
        second = self._follow(self.other, email_announcements=True, email_new_events=True)
        with self.captureOnCommitCallbacks(execute=True):
            update_follow_preferences(
                follow=first,
                user=self.follower,
                notify_announcements=False,
            )
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertFalse(first.notify_announcements)
        self.assertFalse(first.email_announcements)
        self.assertTrue(second.email_announcements)
        self.assertTrue(second.email_new_events)

    def test_unfollow_revokes_only_follow_sourced_contact_consent(self):
        follow = self._follow(email_announcements=True)
        with self.captureOnCommitCallbacks(execute=True):
            unfollow_organization(follow=follow, user=self.follower)
        contact = CRMContact.objects.get(organization=self.organization, user=self.follower)
        self.assertEqual(contact.marketing_consent, MarketingConsent.UNSUBSCRIBED)
        self.assertFalse(OrganizationFollow.objects.filter(organization=self.organization, user=self.follower).exists())

    def test_newly_published_event_notifies_followers_once(self):
        self._follow(notify_new_events=True, email_new_events=False)
        event = Event.objects.create(
            organizer=self.owner,
            organization=self.organization,
            title="Culture Night",
            status=EventStatus.DRAFT,
            visibility=EventVisibility.PUBLIC,
            start_at=timezone.now() + timedelta(days=5),
            end_at=timezone.now() + timedelta(days=5, hours=4),
        )
        event.status = EventStatus.PUBLISHED
        event.published_at = timezone.now()
        with self.captureOnCommitCallbacks(execute=True):
            event.save(update_fields=["status", "published_at", "updated_at"])
        self.assertEqual(
            Notification.objects.filter(recipient=self.follower, metadata__event_id=str(event.pk)).count(),
            1,
        )
        self.assertFalse(
            NotificationDelivery.objects.filter(notification__metadata__event_id=str(event.pk)).exists()
        )
        with self.captureOnCommitCallbacks(execute=True):
            event.save(update_fields=["updated_at"])
        self.assertEqual(
            Notification.objects.filter(recipient=self.follower, metadata__event_id=str(event.pk)).count(),
            1,
        )

    def test_follow_web_and_api_are_owned_by_current_user(self):
        self.client.force_login(self.follower)
        response = self.client.post(reverse("organizer_public:follow-toggle", kwargs={"slug": self.organization.slug}))
        self.assertEqual(response.status_code, 302)
        follow = OrganizationFollow.objects.get(organization=self.organization, user=self.follower)
        response = self.client.patch(
            reverse("organizations_api:follow-detail", kwargs={"pk": follow.pk}),
            data='{"email_announcements": true}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        follow.refresh_from_db()
        self.assertTrue(follow.email_announcements)

        stranger = User.objects.create_user(username="stranger", email="stranger@example.com", password="Strong-password-2026!")
        self.client.force_login(stranger)
        self.assertEqual(
            self.client.delete(reverse("organizations_api:follow-detail", kwargs={"pk": follow.pk})).status_code,
            404,
        )
