"""D1/D2: one Dossier identity under distinct authorized actor lenses."""
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import User
from authorization.constants import SystemRoleCode
from authorization.services import grant_space_role
from objectives.models import ProjectDossierLink
from objectives.services import create_dossier, create_project
from organizations.models import Organization


class DossierActorContextTests(TestCase):
    def setUp(self):
        self.viewer = User.objects.create_user(username="d1-viewer")
        self.outsider = User.objects.create_user(username="d1-outsider")
        self.a = Organization.objects.create(
            name="Espace A", slug="d1-space-a", created_by=self.viewer,
        )
        self.b = Organization.objects.create(
            name="Espace B", slug="d1-space-b", created_by=self.viewer,
        )
        for space in (self.a, self.b):
            grant_space_role(
                profile=self.viewer, space=space, role=SystemRoleCode.SPACE_OWNER,
                granted_by=self.viewer,
            )
        self.dossier = create_dossier(
            actor=self.viewer, owning_space=self.a, title="Dossier unique",
        )
        self.other_dossier = create_dossier(
            actor=self.viewer, owning_space=self.b, title="Autre Dossier",
        )
        self.personal = create_dossier(
            actor=self.viewer, owner_profile=self.viewer, title="Dossier personnel",
        )
        self.project_a = create_project(
            actor=self.viewer, owning_space=self.a, title="Projet A",
        )
        self.project_b = create_project(
            actor=self.viewer, owning_space=self.b, title="Projet B",
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.viewer)

    def scope(self, space):
        return {"context": "space", "space": space.slug}

    def detail(self, dossier):
        return reverse("objectives_api:dossier-detail", args=[dossier.pk])

    def actions(self, dossier):
        return reverse("objectives_api:dossier-actions", args=[dossier.pk])

    def test_same_identity_but_space_scoped_read_and_candidates(self):
        unscoped = self.client.get(self.detail(self.dossier))
        scoped = self.client.get(self.detail(self.dossier), self.scope(self.a))
        self.assertEqual(unscoped.status_code, 200, unscoped.data)
        self.assertEqual(scoped.status_code, 200, scoped.data)
        data = scoped.data["data"]
        self.assertEqual(
            unscoped.data["data"]["identity"], data["identity"],
        )
        self.assertEqual(data["actor_context"]["space"]["id"], str(self.a.pk))
        self.assertEqual(data["viewer"]["id"], str(self.viewer.pk))
        self.assertEqual(data["owner"]["id"], str(self.a.pk))
        self.assertEqual(data["owner"]["slug"], self.a.slug)
        self.assertEqual(
            [row["id"] for row in data["candidates"]["projects"]],
            [str(self.project_a.pk)],
        )
        self.assertIn("?context=space&space=" + self.a.slug, data["links"]["actions"])
        self.assertEqual(
            self.client.get(self.detail(self.dossier), self.scope(self.b)).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(self.detail(self.personal), self.scope(self.a)).status_code,
            404,
        )

    def test_collections_and_project_are_narrowed_by_space_not_user_override(self):
        response = self.client.get(
            reverse("objectives_api:dossier-list"), self.scope(self.a),
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(
            [row["id"] for row in response.data["data"]["items"]],
            [str(self.dossier.pk)],
        )
        self.assertEqual(
            response.data["data"]["actor"]["id"], str(self.viewer.pk),
        )
        project_url = reverse("objectives_api:project-detail", args=[self.project_b.pk])
        self.assertEqual(self.client.get(project_url, self.scope(self.a)).status_code, 404)
        self.assertEqual(self.client.get(project_url, self.scope(self.b)).status_code, 200)

    def test_scoped_mutations_cannot_target_other_space(self):
        wrong = self.client.patch(
            self.detail(self.dossier) + "?context=space&space=" + self.b.slug,
            {"title": "Incorrect"},
            format="json",
        )
        self.assertEqual(wrong.status_code, 404)
        denied = self.client.post(
            self.actions(self.dossier) + "?context=space&space=" + self.a.slug,
            {"action": "project_set", "project_id": str(self.project_b.pk)},
            format="json",
        )
        self.assertEqual(denied.status_code, 404)
        self.assertFalse(ProjectDossierLink.objects.filter(dossier=self.dossier, is_active=True).exists())
        accepted = self.client.post(
            self.actions(self.dossier) + "?context=space&space=" + self.a.slug,
            {"action": "project_set", "project_id": str(self.project_a.pk)},
            format="json",
        )
        self.assertEqual(accepted.status_code, 200, accepted.data)
        self.assertEqual(
            ProjectDossierLink.objects.get(dossier=self.dossier, is_active=True).project_id,
            self.project_a.pk,
        )
        self.dossier.refresh_from_db()
        self.assertEqual(self.dossier.title, "Dossier unique")

    def test_rejects_invalid_or_impostor_context_and_denies_outsider(self):
        for query in (
            {"space": self.a.slug},
            {"context": "space"},
            {"context": "unknown"},
            {"context": "space", "space": self.a.slug,
             "profile_id": str(self.viewer.pk)},
            {"context": "space", "space": self.a.slug,
             "actor_id": str(self.viewer.pk)},
        ):
            self.assertEqual(self.client.get(self.detail(self.dossier), query).status_code, 400)
        self.client.force_authenticate(user=self.outsider)
        self.assertEqual(
            self.client.get(self.detail(self.dossier), self.scope(self.a)).status_code,
            404,
        )
        self.assertEqual(
            self.client.post(
                self.actions(self.dossier) + "?context=space&space=" + self.a.slug,
                {"action": "lifecycle", "lifecycle": "active"},
                format="json",
            ).status_code,
            404,
        )
