"""Contract of the private organizer collection used by Flutter local-first.

The collection exists even when empty, and does not confuse 404 (unknown
resource) with the absence of personal Projects/Dossiers/Journeys.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from rest_framework.test import APIClient

from activities.models import Activity
from journeys.models import Journey, JourneyStatus, WorkflowKind
from objectives.services import (
    create_dossier, create_project, link_dossier_to_project, link_journey,
)


User = get_user_model()


class OrganizerCollectionContractTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="organizer-owner", password="TestPassword123!"
        )
        self.other = User.objects.create_user(
            username="organizer-other", password="TestPassword123!"
        )
        self.client = APIClient()
        self.url = reverse("objectives_api:organizer")

    def _get(self, profile, params=None):
        self.client.force_authenticate(user=profile)
        return self.client.get(self.url, params or {"limit": 50, "offset": 0})

    def _journey(self, owner, title):
        activity = Activity.objects.create(
            title=title, owner_profile=owner, created_by=owner
        )
        return Journey.objects.create(
            initiated_by=owner, beneficiary=owner, activity=activity,
            workflow=WorkflowKind.SERVICE, status=JourneyStatus.DRAFT,
        )

    def test_empty_authenticated_collection_is_a_successful_first_page(self):
        response = self._get(self.owner)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["meta"]["projection"],
                         "objective.organizer.collection")
        data = response.data["data"]
        self.assertEqual(data["actor"]["id"], str(self.owner.pk))
        self.assertEqual(data["items"], [])
        self.assertEqual(data["page"]["offset"], 0)
        self.assertFalse(data["page"]["has_more"])

    def test_unauthenticated_collection_is_not_public(self):
        self.client.force_authenticate(user=None)
        response = self.client.get(self.url)
        self.assertIn(response.status_code, (401, 403))

    def test_mixed_collection_uses_canonical_identities_and_visible_parents(self):
        project = create_project(
            actor=self.owner, owner_profile=self.owner, title="Formation"
        )
        dossier = create_dossier(
            actor=self.owner, owner_profile=self.owner, title="Inscription"
        )
        journey = self._journey(self.owner, "Envoyer le dossier")
        link_dossier_to_project(
            actor=self.owner, project=project, dossier=dossier
        )
        link_journey(actor=self.owner, dossier=dossier, journey=journey)

        response = self._get(self.owner)
        self.assertEqual(response.status_code, 200)
        data = response.data["data"]
        items = {(row["kind"], row["id"]): row for row in data["items"]}
        self.assertIn(("project", str(project.pk)), items)
        self.assertIn(("dossier", str(dossier.pk)), items)
        self.assertIn(("journey", str(journey.pk)), items)
        self.assertEqual(
            items[("dossier", str(dossier.pk))]["project_id"],
            str(project.pk),
        )
        self.assertEqual(
            items[("journey", str(journey.pk))]["dossier_ids"],
            [str(dossier.pk)],
        )
        self.assertEqual(data["actor"]["id"], str(self.owner.pk))

    def test_private_objects_and_links_do_not_leak_to_another_profile(self):
        project = create_project(
            actor=self.owner, owner_profile=self.owner, title="Projet secret"
        )
        dossier = create_dossier(
            actor=self.owner, owner_profile=self.owner, title="Dossier secret"
        )
        journey = self._journey(self.owner, "Journey privée")
        link_dossier_to_project(
            actor=self.owner, project=project, dossier=dossier
        )
        link_journey(actor=self.owner, dossier=dossier, journey=journey)

        response = self._get(self.other)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["items"], [])

    def test_collection_pagination_has_stable_page_identity(self):
        for number in range(3):
            create_project(
                actor=self.owner, owner_profile=self.owner,
                title=f"Projet {number}",
            )
        first = self._get(self.owner, {"limit": 2, "offset": 0})
        second = self._get(self.owner, {"limit": 2, "offset": 2})
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertTrue(first.data["data"]["page"]["has_more"])
        self.assertEqual(first.data["data"]["page"]["next_offset"], 2)
        self.assertEqual(second.data["data"]["page"]["offset"], 2)
        first_ids = {row["id"] for row in first.data["data"]["items"]}
        second_ids = {row["id"] for row in second.data["data"]["items"]}
        self.assertFalse(first_ids & second_ids)

    def test_invalid_page_arguments_return_400_not_a_revocation(self):
        response = self._get(self.owner, {"limit": 0, "offset": 0})
        self.assertEqual(response.status_code, 400)
