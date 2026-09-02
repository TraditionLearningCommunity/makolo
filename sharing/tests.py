from datetime import timedelta
from urllib.parse import parse_qs, urlparse

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from access.models import Access
from activities.models import (
    Activity,
    ActivityStatus,
    ActivityVisibility,
    Occurrence,
    OccurrenceStatus,
)
from authorization.models import Mandate
from commerce.models import CommerceOrder
from journeys.models import Journey
from opportunities.models import (
    Opportunity,
    OpportunityKind,
    OpportunityPublicationStatus,
    OpportunityRevision,
)
from payments.models import Payment

from .models import ShareIntent, ShareStatus
from .services import (
    create_activity_share,
    create_opportunity_share,
    revoke_share_link,
    token_digest,
)


User = get_user_model()


@override_settings(MAKOLO_PUBLIC_BASE_URL="https://makolo.example")
class SharingP1Tests(TestCase):
    password = "Strong-sharing-password-2026!"

    def setUp(self):
        self.creator = User.objects.create_user(
            username="sharing-creator",
            email="sharing-creator@makolo.test",
            password=self.password,
        )
        self.recipient = User.objects.create_user(
            username="sharing-recipient",
            email="sharing-recipient@makolo.test",
            password=self.password,
        )
        self.activity = Activity.objects.create(
            owner_profile=self.creator,
            created_by=self.creator,
            title="Formation secourisme",
            short_description="Apprendre les gestes essentiels.",
            status=ActivityStatus.PUBLISHED,
            visibility=ActivityVisibility.PUBLIC,
        )
        start_at = timezone.now() + timedelta(days=10)
        self.occurrence = Occurrence.objects.create(
            activity=self.activity,
            label="Session du 17 octobre",
            start_at=start_at,
            end_at=start_at + timedelta(hours=2),
            timezone="Europe/Brussels",
            status=OccurrenceStatus.SCHEDULED,
        )
        self.opportunity = Opportunity.objects.create(
            kind=OpportunityKind.SCHOLARSHIP,
            created_by=self.creator,
        )
        self.revision = self._publish_revision(version=1, title="Bourse Makolo 2026")
        self._make_current(self.revision)

    def _publish_revision(self, *, version, title):
        revision = OpportunityRevision.objects.create(
            opportunity=self.opportunity,
            version=version,
            title=title,
            summary=f"Résumé public v{version}",
            issuer_name="Fondation Makolo",
            timezone="Europe/Brussels",
            created_by=self.creator,
        )
        revision.published_at = timezone.now()
        revision._allow_publication = True
        revision.save(update_fields=["published_at"])
        return revision

    def _make_current(self, revision):
        self.opportunity.publication_status = OpportunityPublicationStatus.PUBLISHED
        self.opportunity.current_revision = revision
        self.opportunity.published_at = revision.published_at
        self.opportunity._allow_lifecycle_transition = True
        self.opportunity.save(
            update_fields=["publication_status", "current_revision", "published_at", "updated_at"]
        )
        self.opportunity.refresh_from_db()

    def test_activity_share_uses_opaque_token_hash_and_explicit_occurrence_subject(self):
        created = create_activity_share(
            created_by=self.creator,
            activity=self.activity,
            occurrence=self.occurrence,
        )
        link = created.envelope.link
        subject = created.envelope.activity_subject

        self.assertGreaterEqual(len(created.raw_token), 40)
        self.assertEqual(link.token_hash, token_digest(created.raw_token))
        self.assertNotEqual(link.token_hash, created.raw_token)
        self.assertEqual(subject.activity_id, self.activity.pk)
        self.assertEqual(subject.occurrence_id, self.occurrence.pk)

    def test_activity_share_rejects_foreign_occurrence_and_private_activity(self):
        other_activity = Activity.objects.create(
            owner_profile=self.creator,
            created_by=self.creator,
            title="Autre activité",
            status=ActivityStatus.PUBLISHED,
            visibility=ActivityVisibility.PUBLIC,
        )
        other_occurrence = Occurrence.objects.create(
            activity=other_activity,
            start_at=timezone.now() + timedelta(days=12),
            timezone="Europe/Brussels",
            status=OccurrenceStatus.SCHEDULED,
        )
        with self.assertRaises(ValidationError):
            create_activity_share(
                created_by=self.creator,
                activity=self.activity,
                occurrence=other_occurrence,
            )

        self.activity.visibility = ActivityVisibility.PRIVATE
        self.activity.save(update_fields=["visibility", "updated_at"])
        with self.assertRaises(ValidationError):
            create_activity_share(created_by=self.creator, activity=self.activity)

    def test_valid_unknown_revoked_and_expired_links_are_safe(self):
        created = create_activity_share(
            created_by=self.creator,
            activity=self.activity,
            occurrence=self.occurrence,
        )
        landing = reverse("sharing:landing", kwargs={"token": created.raw_token})
        self.assertEqual(self.client.get(landing).status_code, 200)
        self.assertEqual(
            self.client.get(reverse("sharing:landing", kwargs={"token": "not-a-real-share"})).status_code,
            404,
        )

        revoke_share_link(envelope=created.envelope, actor=self.creator)
        self.assertEqual(self.client.get(landing).status_code, 404)
        created.envelope.refresh_from_db()
        self.assertEqual(created.envelope.status, ShareStatus.REVOKED)

        expiring = create_activity_share(
            created_by=self.creator,
            activity=self.activity,
            occurrence=self.occurrence,
            expires_at=timezone.now() + timedelta(minutes=5),
        )
        expiring.envelope.expires_at = timezone.now() - timedelta(seconds=1)
        expiring.envelope.save(update_fields=["expires_at", "updated_at"])
        self.assertEqual(
            self.client.get(
                reverse("sharing:landing", kwargs={"token": expiring.raw_token})
            ).status_code,
            404,
        )

    def test_anonymous_get_keeps_occurrence_context_and_creates_no_business_state_or_permission(self):
        created = create_activity_share(
            created_by=self.creator,
            activity=self.activity,
            occurrence=self.occurrence,
        )
        counts_before = {
            "journeys": Journey.objects.count(),
            "orders": CommerceOrder.objects.count(),
            "payments": Payment.objects.count(),
            "accesses": Access.objects.count(),
            "mandates": Mandate.objects.count(),
        }
        self.client.logout()
        response = self.client.get(
            reverse("sharing:landing", kwargs={"token": created.raw_token})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.activity.title)
        self.assertContains(response, self.occurrence.label)
        self.assertContains(response, self.occurrence.start_at.strftime("%Y"))
        counts_after = {
            "journeys": Journey.objects.count(),
            "orders": CommerceOrder.objects.count(),
            "payments": Payment.objects.count(),
            "accesses": Access.objects.count(),
            "mandates": Mandate.objects.count(),
        }
        self.assertEqual(counts_after, counts_before)

    def test_share_does_not_make_activity_public_after_visibility_changes(self):
        created = create_activity_share(
            created_by=self.creator,
            activity=self.activity,
            occurrence=self.occurrence,
        )
        Activity.objects.filter(pk=self.activity.pk).update(visibility=ActivityVisibility.PRIVATE)
        response = self.client.get(
            reverse("sharing:landing", kwargs={"token": created.raw_token})
        )
        self.assertEqual(response.status_code, 404)

    def test_opportunity_share_keeps_shared_revision_but_renders_current_published_revision(self):
        created = create_opportunity_share(
            created_by=self.creator,
            opportunity_revision=self.revision,
            intent=ShareIntent.START_JOURNEY,
        )
        revision_two = self._publish_revision(version=2, title="Bourse Makolo 2026 — mise à jour")
        self._make_current(revision_two)

        response = self.client.get(
            reverse("sharing:landing", kwargs={"token": created.raw_token})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, revision_two.title)
        self.assertContains(response, "mise à jour depuis la création de ce partage")
        created.envelope.opportunity_subject.refresh_from_db()
        self.assertEqual(
            created.envelope.opportunity_subject.opportunity_revision_id,
            self.revision.pk,
        )

    def test_action_authentication_returns_to_share_intent_without_creating_journey(self):
        created = create_opportunity_share(
            created_by=self.creator,
            opportunity_revision=self.revision,
            intent=ShareIntent.START_JOURNEY,
        )
        action_url = reverse("sharing:action", kwargs={"token": created.raw_token})
        journey_count = Journey.objects.count()

        response = self.client.get(action_url)
        self.assertEqual(response.status_code, 302)
        parsed = urlparse(response["Location"])
        self.assertEqual(parsed.path, reverse("core:login"))
        self.assertEqual(parse_qs(parsed.query)["next"], [action_url])
        self.assertEqual(Journey.objects.count(), journey_count)

        self.client.force_login(self.recipient)
        response = self.client.get(action_url)
        self.assertEqual(response.status_code, 302)
        parsed = urlparse(response["Location"])
        self.assertEqual(parsed.path, reverse("services:list"))
        self.assertEqual(parse_qs(parsed.query)["opportunity"], [str(self.opportunity.pk)])
        self.assertEqual(Journey.objects.count(), journey_count)

    def test_share_create_ui_endpoints_and_qr_use_safe_link(self):
        self.client.force_login(self.creator)
        response = self.client.post(
            reverse("sharing:create-occurrence", kwargs={"occurrence_id": self.occurrence.pk})
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["url"].startswith("https://makolo.example/s/"))
        self.assertNotIn(str(self.creator.pk), payload["url"])

        token = payload["url"].rstrip("/").split("/")[-1]
        qr_response = self.client.get(reverse("sharing:qr", kwargs={"token": token}))
        self.assertEqual(qr_response.status_code, 200)
        self.assertEqual(qr_response["Content-Type"], "image/png")

        opportunity_response = self.client.get(
            reverse("opportunities:detail", kwargs={"pk": self.opportunity.pk})
        )
        self.assertContains(opportunity_response, "Partager")
        occurrence_response = self.client.get(
            reverse("discovery:activity-detail", kwargs={"occurrence_id": self.occurrence.pk})
        )
        self.assertContains(occurrence_response, "Partager")
