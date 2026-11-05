from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from objectives.models import Dossier, Project


User = get_user_model()


class ObjectiveCollectionAPIContractTests(TestCase):
    def setUp(self):
        self.viewer = User.objects.create_user(
            username="objective-collection-a",
            email="objective-collection-a@example.test",
            password="test-only",
        )
        self.outsider = User.objects.create_user(
            username="objective-collection-b",
            email="objective-collection-b@example.test",
            password="test-only",
        )
        self.client = APIClient()

    def dossier(self, title, owner):
        return Dossier.objects.create(
            title=title,
            created_by=owner,
            owner_profile=owner,
        )

    def project(self, title, owner):
        return Project.objects.create(
            title=title,
            created_by=owner,
            owner_profile=owner,
        )

    def test_dossiers_are_authorized_and_paginated_without_actor_override(self):
        own = [self.dossier(f"Dossier {index}", self.viewer) for index in range(3)]
        secret = self.dossier("Dossier privé", self.outsider)
        self.client.force_authenticate(self.viewer)
        first = self.client.get("/api/v1/objectives/dossiers/?offset=0&limit=2")
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json()["meta"]["projection"], "objective.dossier.collection")
        data = first.json()["data"]
        self.assertEqual(data["actor"], {"type": "profile", "id": str(self.viewer.pk)})
        self.assertEqual(len(data["items"]), 2)
        self.assertTrue(data["page"]["has_more"])
        self.assertEqual(data["page"]["next_offset"], 2)
        self.assertTrue(all(row["relation"] == "mine" for row in data["items"]))
        last = self.client.get("/api/v1/objectives/dossiers/?offset=2&limit=2")
        self.assertEqual(last.status_code, 200)
        self.assertFalse(last.json()["data"]["page"]["has_more"])
        returned_ids = {row["id"] for row in data["items"] + last.json()["data"]["items"]}
        self.assertEqual(returned_ids, {str(row.pk) for row in own})
        self.assertNotIn(str(secret.pk), returned_ids)

        self.client.force_authenticate(self.outsider)
        other_page = self.client.get("/api/v1/objectives/dossiers/")
        self.assertEqual(other_page.status_code, 200)
        self.assertEqual(
            [row["id"] for row in other_page.json()["data"]["items"]],
            [str(secret.pk)],
        )

    def test_projects_and_bad_page_arguments_are_scoped(self):
        project = self.project("Mon projet durable", self.viewer)
        other = self.project("Projet privé", self.outsider)
        self.client.force_authenticate(self.viewer)
        response = self.client.get("/api/v1/objectives/projects/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["meta"]["projection"], "objective.project.collection")
        rows = response.json()["data"]["items"]
        self.assertEqual([row["id"] for row in rows], [str(project.pk)])
        self.assertNotIn(str(other.pk), [row["id"] for row in rows])
        for query in ["?limit=0", "?limit=999", "?offset=-1", "?offset=none"]:
            self.assertEqual(
                self.client.get("/api/v1/objectives/projects/" + query).status_code,
                400,
            )

    def test_unauthenticated_collection_is_not_public(self):
        self.dossier("Privé", self.viewer)
        self.client.force_authenticate(user=None)
        self.assertIn(
            self.client.get("/api/v1/objectives/dossiers/").status_code,
            [401, 403],
        )
        self.assertIn(
            self.client.get("/api/v1/objectives/projects/").status_code,
            [401, 403],
        )
