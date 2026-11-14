"""Authority and actor-lens regression tests for starting a realization.

Creation remains owned by Objectives services; a selected Space is a scope
hint, never a substitute for an effective management permission.
"""
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import Client, TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import User
from authorization.constants import SystemRoleCode
from authorization.models import AuthorityScope, Role
from authorization.services import grant_project_role, grant_space_role
from objectives.models import Dossier, Project
from objectives.services import create_project
from organizations.models import Organization


class CollectiveCreationAuthorityTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="collective-create-owner")
        self.other = User.objects.create_user(username="collective-create-outsider")
        self.space = Organization.objects.create(
            name="Atelier collectif", slug="collective-create-space",
            created_by=self.owner,
        )
        grant_space_role(
            profile=self.owner, space=self.space,
            role=SystemRoleCode.SPACE_OWNER, granted_by=self.owner,
        )
        self.api = APIClient()
        self.web = Client()
        self.space_query = "?context=space&space=" + self.space.slug

    def test_api_denies_unmandated_space_creation_without_writing(self):
        self.api.force_authenticate(user=self.other)
        for name, model in (
            ("objectives_api:dossier-list", Dossier),
            ("objectives_api:project-list", Project),
        ):
            with self.subTest(kind=name):
                before = model.objects.count()
                response = self.api.post(
                    reverse(name) + self.space_query,
                    {"title": "Non autorisé"}, format="json",
                )
                self.assertEqual(response.status_code, 403, response.data)
                self.assertEqual(response.data["detail"], "Action non autorisée.")
                self.assertEqual(model.objects.count(), before)

    def test_api_creates_each_object_under_the_authorized_space_only(self):
        self.api.force_authenticate(user=self.owner)
        for name, model in (
            ("objectives_api:dossier-list", Dossier),
            ("objectives_api:project-list", Project),
        ):
            with self.subTest(kind=name):
                response = self.api.post(
                    reverse(name) + self.space_query,
                    {"title": "Réalisation collective"}, format="json",
                )
                self.assertEqual(response.status_code, 201, response.data)
                created = model.objects.get(pk=response.data["id"])
                self.assertEqual(created.owning_space_id, self.space.pk)
                self.assertIsNone(created.owner_profile_id)

    def test_project_manager_cannot_create_child_on_anothers_behalf(self):
        project = create_project(
            actor=self.owner, owner_profile=self.owner, title="Projet partagé",
        )
        manager_role = Role.objects.get(
            scope_type=AuthorityScope.PROJECT,
            code=SystemRoleCode.PROJECT_MANAGER,
        )
        grant_project_role(
            profile=self.other, project=project,
            role=manager_role, granted_by=self.owner,
        )
        self.api.force_authenticate(user=self.other)
        before = Dossier.objects.count()
        response = self.api.post(
            reverse("objectives_api:project-dossiers", args=[project.pk]),
            {"action": "create", "title": "Coordination non autorisée"},
            format="json",
        )
        self.assertEqual(response.status_code, 403, response.data)
        self.assertEqual(Dossier.objects.count(), before)

    def test_web_creation_never_confirms_owner_refusal_after_entry_check(self):
        self.web.force_login(self.owner)
        for name, service, model in (
            ("objectives:dossier-create", "create_dossier", Dossier),
            ("objectives:project-create", "create_project", Project),
        ):
            with self.subTest(kind=name):
                before = model.objects.count()
                with patch(
                    "objectives.views." + service,
                    side_effect=PermissionDenied("Mandat révoqué"),
                ) as denied:
                    response = self.web.post(
                        reverse(name) + self.space_query,
                        {"title": "Création interrompue"},
                    )
                self.assertEqual(response.status_code, 404)
                denied.assert_called_once()
                self.assertEqual(model.objects.count(), before)

    def test_web_validation_error_keeps_the_form_and_no_success(self):
        self.web.force_login(self.owner)
        for name, service in (
            ("objectives:dossier-create", "create_dossier"),
            ("objectives:project-create", "create_project"),
        ):
            with self.subTest(kind=name):
                with patch(
                    "objectives.views." + service,
                    side_effect=ValidationError("Données refusées"),
                ):
                    response = self.web.post(
                        reverse(name) + self.space_query,
                        {"title": "À corriger"},
                    )
                self.assertEqual(response.status_code, 200)
                self.assertIn(
                    "Données refusées",
                    list(response.context["form"].non_field_errors()),
                )
