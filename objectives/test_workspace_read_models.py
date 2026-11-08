"""Integration contracts for the canonical Project/Dossier/Journey handoffs.

These assertions intentionally exercise the full API views and serializers
rather than constructing synthetic UI payloads.
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


class ObjectiveWorkspaceReadModelsTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="workspace-owner", password="TestPassword123!"
        )
        self.stranger = User.objects.create_user(
            username="workspace-stranger", password="TestPassword123!"
        )
        self.project = create_project(
            actor=self.owner, title="Mon parcours",
            owner_profile=self.owner,
        )
        self.dossier = create_dossier(
            actor=self.owner, title="Constituer le dossier",
            owner_profile=self.owner,
        )
        self.activity = Activity.objects.create(
            owner_profile=self.owner, created_by=self.owner,
            title="Déposer une demande",
        )
        self.journey = Journey.objects.create(
            initiated_by=self.owner, beneficiary=self.owner,
            activity=self.activity, workflow=WorkflowKind.SERVICE,
            status=JourneyStatus.DRAFT,
        )
        link_dossier_to_project(
            actor=self.owner, project=self.project, dossier=self.dossier
        )
        link_journey(
            actor=self.owner, dossier=self.dossier, journey=self.journey
        )
        self.client = APIClient()

    def test_project_workspace_exposes_only_real_linked_dossiers(self):
        self.client.force_authenticate(user=self.owner)
        result = self.client.get(
            reverse("objectives_api:project-detail", args=[self.project.pk])
        )
        self.assertEqual(result.status_code, 200)
        view = result.data["data"]
        self.assertEqual(view["identity"]["id"], str(self.project.pk))
        self.assertEqual(view["visible_dossiers"][0]["id"], str(self.dossier.pk))
        self.assertEqual(view["visible_dossiers"][0]["kind"], "dossier")
        self.assertIn("project.dossier.link", view["capabilities"])

    def test_dossier_workspace_exposes_all_visible_journeys_and_readiness(self):
        self.client.force_authenticate(user=self.owner)
        result = self.client.get(
            reverse("objectives_api:dossier-detail", args=[self.dossier.pk])
        )
        self.assertEqual(result.status_code, 200)
        view = result.data["data"]
        self.assertEqual(view["identity"]["id"], str(self.dossier.pk))
        self.assertEqual(
            view["parent_project"]["id"], str(self.project.pk)
        )
        self.assertTrue(view["visible_journeys_complete"])
        self.assertEqual(len(view["visible_journeys"]), 1)
        self.assertEqual(
            view["visible_journeys"][0]["id"], str(self.journey.pk)
        )
        self.assertIn("readiness", view)
        self.assertIn("visible_items", view)  # historical consumer contract

    def test_private_horizon_and_dossier_cannot_be_opened_by_other_profile(self):
        self.client.force_authenticate(user=self.stranger)
        for route, pk in [
            ("objectives_api:project-detail", self.project.pk),
            ("objectives_api:dossier-detail", self.dossier.pk),
        ]:
            result = self.client.get(reverse(route, args=[pk]))
            self.assertEqual(result.status_code, 404)
