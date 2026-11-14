"""Stage-07 Sharing: owner-confirmed link, revocation, recipient isolation."""
import json
from urllib.parse import urlsplit

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from opportunities.models import (
    Opportunity, OpportunityKind, OpportunityPublicationStatus,
    OpportunityRevision,
)
from sharing.models import ShareEnvelope, ShareStatus

User = get_user_model()


class DiscoveryStage07SharingTests(TestCase):
    def setUp(self):
        self.sender = User.objects.create_user(
            username="share-07-sender", email="sender07@example.test", password="test",
        )
        self.recipient = User.objects.create_user(
            username="share-07-recipient", email="recipient07@example.test", password="test",
        )
        self.opportunity = Opportunity.objects.create(
            kind=OpportunityKind.SCHOLARSHIP, created_by=self.sender,
        )
        revision = OpportunityRevision.objects.create(
            opportunity=self.opportunity,
            version=1,
            title="Bourse partagée 07",
            summary="Offre publiée",
            issuer_name="Fondation",
            created_by=self.sender,
        )
        now = timezone.now()
        OpportunityRevision.objects.filter(pk=revision.pk).update(published_at=now)
        Opportunity.objects.filter(pk=self.opportunity.pk).update(
            current_revision=revision,
            publication_status=OpportunityPublicationStatus.PUBLISHED,
            published_at=now,
        )
        self.path = reverse("sharing_api:possibility", kwargs={
            "family": "opportunity", "item_id": self.opportunity.pk,
        })

    def post_share(self, body=None):
        return self.client.post(
            self.path,
            data=json.dumps(body or {"intent": "view"}),
            content_type="application/json",
        )

    def test_unauthenticated_share_does_not_create_envelope(self):
        response = self.post_share()
        self.assertIn(response.status_code, (401, 403))
        self.assertFalse(ShareEnvelope.objects.exists())

    def test_owner_confirmed_public_link_resolves_only_while_authorized(self):
        self.client.force_login(self.sender)
        response = self.post_share()
        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertEqual(payload["state"], "link")
        self.assertIn(urlsplit(payload["url"]).scheme, ("http", "https"))
        token = urlsplit(payload["url"]).path.rstrip("/").rsplit("/", 1)[-1]
        self.client.logout()
        resolve = reverse("sharing_api:resolve", kwargs={"token": token})
        resolved = self.client.get(resolve)
        self.assertEqual(resolved.status_code, 200)
        self.assertEqual(resolved.json()["family"], "opportunity")
        self.assertEqual(resolved.json()["id"], str(self.opportunity.pk))
        self.assertEqual(resolved["Cache-Control"], "no-store")

        envelope = ShareEnvelope.objects.first()
        envelope.status = ShareStatus.REVOKED
        envelope.revoked_at = timezone.now()
        envelope.save()
        self.assertEqual(self.client.get(resolve).status_code, 404)

    def test_withdrawn_owner_subject_is_not_shareable_or_resolvable(self):
        self.client.force_login(self.sender)
        created = self.post_share()
        self.assertEqual(created.status_code, 201)
        token = urlsplit(created.json()["url"]).path.rstrip("/").rsplit("/", 1)[-1]
        Opportunity.objects.filter(pk=self.opportunity.pk).update(
            publication_status=OpportunityPublicationStatus.WITHDRAWN,
        )
        self.assertEqual(self.post_share().status_code, 404)
        self.client.logout()
        self.assertEqual(
            self.client.get(reverse("sharing_api:resolve", kwargs={"token": token})).status_code,
            404,
        )

    def test_explicit_empty_internal_recipient_does_not_fall_back_to_link(self):
        self.client.force_login(self.sender)
        response = self.post_share({"intent": "view", "recipient_id": ""})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(ShareEnvelope.objects.exists())

    def test_invalid_internal_recipient_is_rejected_without_a_delivery(self):
        self.client.force_login(self.sender)
        response = self.post_share({"intent": "view", "recipient_id": "not-a-uuid"})
        self.assertEqual(response.status_code, 400)
        from sharing.models import ShareDelivery
        self.assertFalse(ShareDelivery.objects.exists())

    def test_private_delivery_cannot_be_resolved_by_another_profile(self):
        # A direct delivery is only valid if the recipient is public/searchable;
        # the canonical owner API produces the delivery identity.
        from accounts.models import UserProfile
        sender_profile, _ = UserProfile.objects.get_or_create(user=self.sender)
        recipient_profile, _ = UserProfile.objects.get_or_create(user=self.recipient)
        recipient_profile.searchable = True
        recipient_profile.save()
        self.client.force_login(self.sender)
        response = self.post_share({
            "intent": "view", "recipient_id": str(recipient_profile.pk),
        })
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["state"], "delivered")
        delivery_id = response.json()["delivery_id"]
        detail = reverse("sharing_api:delivery", kwargs={"delivery_id": delivery_id})
        self.client.logout()
        self.assertIn(self.client.get(detail).status_code, (401, 403))
        self.client.force_login(self.sender)
        self.assertEqual(self.client.get(detail).status_code, 403)
        self.client.force_login(self.recipient)
        self.assertEqual(self.client.get(detail).status_code, 200)
