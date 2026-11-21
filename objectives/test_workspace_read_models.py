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
from objectives.models import DossierJourneyDependency, DossierJourneyLink, ProjectDossierLink
from objectives.services import (
    add_dependency, create_dossier, create_project,
    link_dossier_to_project, link_journey,
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

    def test_many_dossiers_shared_journey_and_dependencies_are_canonical(self):
        second = create_dossier(
            actor=self.owner, owner_profile=self.owner, title="Pièces complémentaires"
        )
        independent = create_dossier(
            actor=self.owner, owner_profile=self.owner, title="Dossier indépendant"
        )
        link_dossier_to_project(
            actor=self.owner, project=self.project, dossier=second
        )
        extra = self._journey(self.owner, "Faire contrôler les pièces")
        required = link_journey(
            actor=self.owner, dossier=second, journey=self.journey
        )
        dependent = link_journey(
            actor=self.owner, dossier=second, journey=extra
        )
        dependency = add_dependency(
            actor=self.owner, dossier=second,
            dependent_link=dependent, required_link=required,
        )
        self.client.force_authenticate(user=self.owner)
        organizer = self.client.get(reverse("objectives_api:organizer"))
        self.assertEqual(organizer.status_code, 200)
        items = organizer.data["data"]["items"]
        journeys = [row for row in items if row["kind"] == "journey"]
        self.assertEqual(len(journeys), 2)
        shared = next(row for row in journeys if row["id"] == str(self.journey.pk))
        self.assertCountEqual(
            shared["dossier_ids"], [str(self.dossier.pk), str(second.pk)],
        )
        project = self.client.get(
            reverse("objectives_api:project-detail", args=[self.project.pk])
        )
        self.assertEqual(project.status_code, 200)
        self.assertCountEqual(
            [row["id"] for row in project.data["data"]["visible_dossiers"]],
            [str(self.dossier.pk), str(second.pk)],
        )
        second_detail = self.client.get(
            reverse("objectives_api:dossier-detail", args=[second.pk])
        )
        self.assertEqual(second_detail.status_code, 200)
        second_data = second_detail.data["data"]
        self.assertCountEqual(
            [row["id"] for row in second_data["visible_journeys"]],
            [str(self.journey.pk), str(extra.pk)],
        )
        self.assertEqual(
            [row["id"] for row in second_data["visible_dependencies"]],
            [str(dependency.pk)],
        )
        independent_data = self.client.get(
            reverse("objectives_api:dossier-detail", args=[independent.pk])
        ).data["data"]
        self.assertIsNone(independent_data["parent_project"])
        self.assertEqual(independent_data["visible_journeys"], [])

    def test_owner_link_unlink_and_relink_preserve_journey_identity(self):
        self.client.force_authenticate(user=self.owner)
        unlink = self.client.post(
            reverse(
                "objectives_api:project-dossier-action",
                args=[self.project.pk, self.dossier.pk],
            ),
            {"action": "unlink"},
            format="json",
        )
        self.assertEqual(unlink.status_code, 200)
        self.assertFalse(ProjectDossierLink.objects.filter(
            project=self.project, dossier=self.dossier, is_active=True,
        ).exists())
        self.assertEqual(
            self.client.get(
                reverse("objectives_api:dossier-detail", args=[self.dossier.pk])
            ).data["data"]["parent_project"],
            None,
        )
        relink = self.client.post(
            reverse("objectives_api:project-dossiers", args=[self.project.pk]),
            {"action": "link", "dossier_id": str(self.dossier.pk)},
            format="json",
        )
        self.assertEqual(relink.status_code, 200)
        self.assertTrue(ProjectDossierLink.objects.filter(
            project=self.project, dossier=self.dossier, is_active=True,
        ).exists())
        remove_journey = self.client.post(
            reverse("objectives_api:dossier-actions", args=[self.dossier.pk]),
            {"action": "unlink_journey", "journey_id": str(self.journey.pk)},
            format="json",
        )
        self.assertEqual(remove_journey.status_code, 200)
        self.assertFalse(DossierJourneyLink.objects.filter(
            dossier=self.dossier, journey=self.journey, is_active=True,
        ).exists())
        self.assertTrue(Journey.objects.filter(pk=self.journey.pk).exists())
        add_again = self.client.post(
            reverse("objectives_api:dossier-actions", args=[self.dossier.pk]),
            {"action": "link_journey", "journey_id": str(self.journey.pk)},
            format="json",
        )
        self.assertEqual(add_again.status_code, 200)
        self.assertTrue(DossierJourneyLink.objects.filter(
            dossier=self.dossier, journey=self.journey, is_active=True,
        ).exists())

    def test_stranger_cannot_mutate_project_dossier_or_journey_links(self):
        initial = ProjectDossierLink.objects.filter(
            project=self.project, dossier=self.dossier, is_active=True,
        ).count()
        self.client.force_authenticate(user=self.stranger)
        cases = (
            (
                reverse("objectives_api:project-dossiers", args=[self.project.pk]),
                {"action": "link", "dossier_id": str(self.dossier.pk)},
            ),
            (
                reverse(
                    "objectives_api:project-dossier-action",
                    args=[self.project.pk, self.dossier.pk],
                ),
                {"action": "unlink"},
            ),
            (
                reverse("objectives_api:dossier-actions", args=[self.dossier.pk]),
                {"action": "unlink_journey", "journey_id": str(self.journey.pk)},
            ),
        )
        for url, body in cases:
            with self.subTest(url=url):
                denied = self.client.post(url, body, format="json")
                self.assertEqual(denied.status_code, 404)
        self.assertEqual(
            ProjectDossierLink.objects.filter(
                project=self.project, dossier=self.dossier, is_active=True,
            ).count(), initial,
        )
        self.assertTrue(Journey.objects.filter(pk=self.journey.pk).exists())
