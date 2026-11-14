"""Stage-07: Watch identity, idempotence, tenant isolation and Save separation."""
import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from discovery.models import DiscoveryWatch
from opportunities.models import (
    Opportunity, OpportunityKind, OpportunityPublicationStatus, OpportunitySave,
    OpportunityRevision,
)

User = get_user_model()


class DiscoveryStage07WatchSaveTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="stage07-owner", email="stage07-owner@example.test",
            password="test-password",
        )
        self.other = User.objects.create_user(
            username="stage07-other", email="stage07-other@example.test",
            password="test-password",
        )
        self.url = reverse("discovery_api:watches")

    def post_json(self, path, body):
        return self.client.post(
            path, data=json.dumps(body), content_type="application/json",
        )

    def patch_json(self, path, body):
        return self.client.patch(
            path, data=json.dumps(body), content_type="application/json",
        )

    def test_watch_requires_authenticated_owner(self):
        response = self.post_json(self.url, {
            "name": "Déplacements", "criteria": {"q": "bus"},
        })
        self.assertIn(response.status_code, (401, 403))
        self.assertEqual(DiscoveryWatch.objects.count(), 0)

    def test_watch_replay_reuses_active_owner_identity_and_does_not_save(self):
        self.client.force_login(self.owner)
        body = {"name": "Veille transport", "criteria": {"q": "bus"}}
        first = self.post_json(self.url, body)
        second = self.post_json(self.url, body)
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        first_watch = first.json()["data"]["watch"]
        second_watch = second.json()["data"]["watch"]
        self.assertEqual(first_watch["id"], second_watch["id"])
        self.assertTrue(first.json()["data"]["created"])
        self.assertFalse(second.json()["data"]["created"])
        self.assertEqual(DiscoveryWatch.objects.filter(owner=self.owner).count(), 1)

    def test_pause_resume_delete_are_explicit_and_private(self):
        self.client.force_login(self.owner)
        response = self.post_json(self.url, {
            "name": "Veille cours", "criteria": {"q": "formation"},
        })
        watch_id = response.json()["data"]["watch"]["id"]
        detail = reverse("discovery_api:watch-detail", kwargs={"watch_id": watch_id})
        paused = self.patch_json(detail, {"status": "paused"})
        self.assertEqual(paused.status_code, 200)
        self.assertEqual(paused.json()["data"]["watch"]["status"], "paused")
        other = self.post_json(self.url, {
            "name": "Veille cours", "criteria": {"q": "formation"},
        })
        self.assertEqual(other.status_code, 201)
        self.assertNotEqual(other.json()["data"]["watch"]["id"], watch_id)
        resumed = self.patch_json(detail, {"status": "active"})
        self.assertEqual(resumed.status_code, 200)
        self.assertEqual(resumed.json()["data"]["watch"]["status"], "active")
        self.client.force_login(self.other)
        self.assertEqual(self.patch_json(detail, {"status": "paused"}).status_code, 404)
        self.assertEqual(self.client.delete(detail).status_code, 404)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.delete(detail).status_code, 204)
        self.assertFalse(DiscoveryWatch.objects.filter(pk=watch_id).exists())

    def test_edit_name_and_criteria_preserves_watch_identity(self):
        self.client.force_login(self.owner)
        created = self.post_json(self.url, {
            "name": "Veille initiale", "criteria": {"q": "bourse"},
        })
        self.assertEqual(created.status_code, 201)
        watch_id = created.json()["data"]["watch"]["id"]
        detail = reverse("discovery_api:watch-detail", kwargs={"watch_id": watch_id})
        renamed = self.patch_json(detail, {"name": "Veille renommée"})
        self.assertEqual(renamed.status_code, 200)
        self.assertEqual(renamed.json()["data"]["watch"]["name"], "Veille renommée")
        changed = self.patch_json(detail, {"criteria": {
            "q": "formation", "place": "Lubumbashi",
        }})
        self.assertEqual(changed.status_code, 200)
        self.assertEqual(changed.json()["data"]["watch"]["id"], watch_id)
        self.assertEqual(changed.json()["data"]["watch"]["criteria"]["q"], "formation")
        self.assertEqual(DiscoveryWatch.objects.filter(owner=self.owner).count(), 1)

    def test_web_watch_create_uses_same_idempotent_owner_transition(self):
        self.client.force_login(self.owner)
        form = reverse("discovery:watch-create")
        body = {"name": "Veille Web", "criteria": json.dumps({"q": "transport"})}
        first = self.client.post(form, data=body)
        second = self.client.post(form, data=body)
        self.assertEqual(first.status_code, 302)
        self.assertEqual(second.status_code, 302)
        self.assertEqual(DiscoveryWatch.objects.filter(
            owner=self.owner, name="Veille Web",
        ).count(), 1)

    def test_bad_watch_criteria_and_status_are_400_not_server_errors(self):
        self.client.force_login(self.owner)
        for criteria in ({}, {"lat": "-11.6"}, {"vertical": "not_supported"}):
            res = self.post_json(self.url, {"name": "Veille", "criteria": criteria})
            self.assertEqual(res.status_code, 400)
        self.assertEqual(
            self.post_json(self.url, {
                "name": "X" * 141, "criteria": {"q": "test"},
            }).status_code, 400,
        )
        created = self.post_json(self.url, {
            "name": "Veille", "criteria": {"q": "test"},
        })
        detail = reverse("discovery_api:watch-detail", kwargs={
            "watch_id": created.json()["data"]["watch"]["id"],
        })
        self.assertEqual(self.patch_json(detail, {"status": "fake"}).status_code, 400)
        self.assertEqual(self.patch_json(detail, {"criteria": {}}).status_code, 400)

    def test_opportunity_save_is_idempotent_and_independent_of_watch(self):
        opportunity = Opportunity.objects.create(
            kind=OpportunityKind.SCHOLARSHIP, created_by=self.owner,
        )
        revision = OpportunityRevision.objects.create(
            opportunity=opportunity, version=1,
            title="Bourse Save 07", summary="Offre publiée",
            issuer_name="Fondation", created_by=self.owner,
        )
        now = timezone.now()
        OpportunityRevision.objects.filter(pk=revision.pk).update(published_at=now)
        Opportunity.objects.filter(pk=opportunity.pk).update(
            current_revision=revision,
            publication_status=OpportunityPublicationStatus.PUBLISHED,
            published_at=now,
        )
        url = reverse("discovery_api:item-saved", kwargs={
            "family": "opportunity", "item_id": opportunity.pk,
        })
        self.client.force_login(self.other)
        saved_first = self.client.put(url)
        saved_again = self.client.put(url)
        self.assertEqual(saved_first.status_code, 200)
        self.assertEqual(saved_again.status_code, 200)
        self.assertEqual(
            saved_again.json()["data"]["item"]["saved"]["state"], "saved",
        )
        self.assertEqual(
            OpportunitySave.objects.filter(profile=self.other, opportunity=opportunity).count(),
            1,
        )
        self.assertFalse(DiscoveryWatch.objects.filter(owner=self.other).exists())
        unsaved = self.client.delete(url)
        self.assertEqual(unsaved.status_code, 200)
        self.assertEqual(
            unsaved.json()["data"]["item"]["saved"]["state"], "not_saved",
        )
        self.assertFalse(
            OpportunitySave.objects.filter(profile=self.other, opportunity=opportunity).exists(),
        )
