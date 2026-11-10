"""D6: Web and API use the same authorized Objectives presentation lens.

These tests exercise Django session views, not only DRF force_authenticate.
Space selection narrows an already-authorized viewer; it never impersonates
another Profile or confers a Mandate.
"""
from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from authorization.constants import SystemRoleCode
from authorization.services import grant_space_role
from objectives.models import ProjectDossierLink
from objectives.services import (
    create_dossier, create_project, link_dossier_to_project,
)
from organizations.models import Organization


class D6WebActorContextTests(TestCase):
    def setUp(self):
        self.viewer = User.objects.create_user(username="d6-web-viewer")
        self.outsider = User.objects.create_user(username="d6-web-outsider")
        self.a = Organization.objects.create(
            name="D6 Espace A", slug="d6-web-a", created_by=self.viewer,
        )
        self.b = Organization.objects.create(
            name="D6 Espace B", slug="d6-web-b", created_by=self.viewer,
        )
        for space in (self.a, self.b):
            grant_space_role(
                profile=self.viewer, space=space,
                role=SystemRoleCode.SPACE_OWNER, granted_by=self.viewer,
            )
        self.pa = create_project(
            actor=self.viewer, owning_space=self.a, title="Projet A",
        )
        self.pb = create_project(
            actor=self.viewer, owning_space=self.b, title="Projet B",
        )
        self.da = create_dossier(
            actor=self.viewer, owning_space=self.a, title="Dossier A",
        )
        self.db = create_dossier(
            actor=self.viewer, owning_space=self.b, title="Dossier B",
        )
        self.independent_a = create_dossier(
            actor=self.viewer, owning_space=self.a, title="A indépendant",
        )
        self.independent_b = create_dossier(
            actor=self.viewer, owning_space=self.b, title="B indépendant",
        )
        link_dossier_to_project(
            actor=self.viewer, project=self.pa, dossier=self.da,
        )
        link_dossier_to_project(
            actor=self.viewer, project=self.pb, dossier=self.db,
        )
        self.client.force_login(self.viewer)

    @staticmethod
    def scope(space):
        return "?context=space&space=" + space.slug

    def project_url(self, project):
        return reverse("objectives:project-detail", args=[project.pk])

    def dossier_url(self, dossier):
        return reverse("objectives:dossier-detail", args=[dossier.pk])

    def test_organizer_and_deep_web_pages_share_the_space_lens(self):
        url = reverse("objectives:organizer")
        a = self.client.get(url + self.scope(self.a))
        b = self.client.get(url + self.scope(self.b))
        personal = self.client.get(url)
        for result in (a, b, personal):
            self.assertEqual(result.status_code, 200)
        self.assertEqual(
            a.context["organizer_data"]["actor_context"]["space"]["slug"],
            self.a.slug,
        )
        self.assertEqual(
            b.context["organizer_data"]["actor_context"]["space"]["slug"],
            self.b.slug,
        )
        def identities(result):
            return {
                (row["kind"], row["id"])
                for row in result.context["organizer_data"]["items"]
            }
        self.assertIn(("project", str(self.pa.pk)), identities(a))
        self.assertNotIn(("project", str(self.pb.pk)), identities(a))
        self.assertIn(("dossier", str(self.db.pk)), identities(b))
        self.assertNotIn(("dossier", str(self.da.pk)), identities(b))
        self.assertIn(("project", str(self.pa.pk)), identities(personal))
        self.assertIn(("project", str(self.pb.pk)), identities(personal))
        self.assertEqual(a.context["scope_query"], self.scope(self.a))
        self.assertContains(a, "context=space&amp;space=" + self.a.slug)

        detail = self.client.get(self.project_url(self.pa) + self.scope(self.a))
        dossier = self.client.get(self.dossier_url(self.da) + self.scope(self.a))
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(dossier.status_code, 200)
        self.assertEqual(detail.context["workspace"]["actor_context"]["kind"], "space")
        self.assertEqual(dossier.context["workspace"]["owner"]["slug"], self.a.slug)
        self.assertEqual(
            dossier.context["workspace"]["parent_project"]["id"],
            str(self.pa.pk),
        )
        self.assertContains(
            detail, self.dossier_url(self.da) + self.scope(self.a),
        )
        self.assertEqual(
            self.client.get(self.project_url(self.pb) + self.scope(self.a)).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(self.dossier_url(self.db) + self.scope(self.a)).status_code,
            404,
        )

    def test_web_forms_show_only_valid_scoped_choices(self):
        project = self.client.get(self.project_url(self.pa) + self.scope(self.a))
        link_form = project.context["link_form"]
        self.assertIsNotNone(link_form)
        choices = set(link_form.fields["dossier"].queryset.values_list("pk", flat=True))
        self.assertIn(self.independent_a.pk, choices)
        self.assertNotIn(self.independent_b.pk, choices)

        dossier = self.client.get(
            self.dossier_url(self.independent_a) + self.scope(self.a),
        )
        target_form = dossier.context["project_form"]
        self.assertIsNotNone(target_form)
        projects = set(target_form.fields["project"].queryset.values_list("pk", flat=True))
        self.assertIn(self.pa.pk, projects)
        self.assertNotIn(self.pb.pk, projects)

    def test_scoped_web_post_cannot_move_to_a_foreign_space(self):
        move = self.client.post(
            reverse(
                "objectives:project-move-dossier",
                args=[self.pa.pk, self.da.pk],
            ) + self.scope(self.a),
            {"target_project_id": str(self.pb.pk)},
        )
        self.assertEqual(move.status_code, 404)
        self.assertEqual(
            ProjectDossierLink.objects.get(
                dossier=self.da, is_active=True,
            ).project_id, self.pa.pk,
        )
        self.assertEqual(
            self.client.post(
                reverse("objectives:dossier-edit", args=[self.db.pk])
                + self.scope(self.a),
                {"title": "Faux droit"},
            ).status_code, 404,
        )
        self.db.refresh_from_db()
        self.assertEqual(self.db.title, "Dossier B")

    def test_web_creation_locks_space_owner_even_if_post_was_forged(self):
        url = reverse("objectives:dossier-create") + self.scope(self.a)
        display = self.client.get(url)
        self.assertEqual(display.status_code, 200)
        self.assertContains(display, self.a.name)
        response = self.client.post(
            url, {
                "title": "D6 créé A",
                "description": "Création Web",
                "owning_space": str(self.b.pk),
            },
        )
        self.assertEqual(response.status_code, 302, response.context if hasattr(response, "context") else response.content)
        from objectives.models import Dossier
        created = Dossier.objects.get(
            owning_space=self.a, title="D6 créé A",
        )
        self.assertEqual(created.owning_space_id, self.a.pk)
        self.assertTrue(response["Location"].endswith(self.scope(self.a)))

    def test_invalid_lens_is_400_and_membership_does_not_grant_access(self):
        url = reverse("objectives:organizer")
        self.assertEqual(
            self.client.get(url + "?context=space").status_code, 400,
        )
        self.assertEqual(
            self.client.get(
                url + "?context=space&space=" + self.a.slug
                + "&viewer_id=" + str(self.outsider.pk),
            ).status_code, 400,
        )
        self.client.force_login(self.outsider)
        self.assertEqual(
            self.client.get(self.project_url(self.pa) + self.scope(self.a)).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(self.dossier_url(self.da) + self.scope(self.a)).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(
                reverse("objectives:project-create") + self.scope(self.a),
            ).status_code, 404,
        )
