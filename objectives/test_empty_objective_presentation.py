"""Empty Objective state is never treated as completed readiness.

These tests exercise the owner-backed readiness projection, not a Flutter-only
fallback. Actor context is always resolved by the server at creation time.
"""
import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from objectives.models import Dossier, Project
from objectives.readiness import resolve_dossier_readiness
from objectives.services import create_dossier, create_project, link_dossier_to_project

User = get_user_model()


class EmptyObjectivePresentationTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="empty-objective-owner")
        self.client = APIClient()
        self.client.force_authenticate(user=self.owner)

    def test_empty_dossier_has_no_readiness_or_fake_action(self):
        dossier = create_dossier(
            actor=self.owner, owner_profile=self.owner, title="Objectif sans démarches",
        )
        readiness = resolve_dossier_readiness(dossier, viewer=self.owner)
        self.assertIsNone(readiness.status)
        self.assertIsNone(readiness.status_label)
        response = self.client.get(reverse(
            "objectives_api:dossier-detail", args=[dossier.pk],
        ))
        self.assertEqual(response.status_code, 200)
        view = response.data["data"]
        self.assertEqual(view["visible_journeys"], [])
        self.assertIsNone(view["readiness"]["state"])
        self.assertIsNone(view["readiness"]["label"])
        self.assertIsNone(view["readiness"]["next_action"])

    def test_empty_linked_dossier_does_not_show_ready_in_project(self):
        project = create_project(
            actor=self.owner, owner_profile=self.owner, title="Projet sans Journey",
        )
        dossier = create_dossier(
            actor=self.owner, owner_profile=self.owner, title="Dossier sans Journey",
        )
        link_dossier_to_project(
            actor=self.owner, project=project, dossier=dossier,
        )
        response = self.client.get(reverse(
            "objectives_api:project-detail", args=[project.pk],
        ))
        self.assertEqual(response.status_code, 200)
        rows = response.data["data"]["visible_dossiers"]
        self.assertEqual(len(rows), 1)
        self.assertIsNone(rows[0]["readiness"]["state"])
        self.assertIsNone(rows[0]["readiness"]["label"])

    def test_personal_project_creation_ignores_no_client_owner_override(self):
        response = self.client.post(
            reverse("objectives_api:project-list"),
            {"title": "Mon projet"}, format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        project = Project.objects.get(pk=response.data["id"])
        self.assertEqual(project.owner_profile_id, self.owner.pk)
        self.assertIsNone(project.owning_space_id)

    def test_personal_creation_rejects_hidden_space_override(self):
        for route in ["objectives_api:project-list", "objectives_api:dossier-list"]:
            response = self.client.post(
                reverse(route),
                {"title": "Objectif", "owning_space_id": str(uuid.uuid4())},
                format="json",
            )
            self.assertEqual(response.status_code, 400)
        self.assertFalse(Project.objects.exists())
        self.assertFalse(Dossier.objects.exists())
