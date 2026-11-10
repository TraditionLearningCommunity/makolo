"""Project collaboration stays scoped to canonical Mandates, not Dossier authority."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from authorization.constants import PermissionCode, SystemRoleCode
from authorization.models import AuthorityScope, Mandate, Role
from authorization.services import can, can_many, effective_permission_codes, grant_dossier_role, grant_project_role
from objectives.services import (
    assign_dossier, create_dossier, create_project, link_dossier_to_project,
)

User = get_user_model()


class ProjectAuthorityIntegrationTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="project-owner")
        self.viewer = User.objects.create_user(username="project-viewer")
        self.manager = User.objects.create_user(username="project-manager")
        self.stranger = User.objects.create_user(username="project-stranger")
        self.project = create_project(
            actor=self.owner, owner_profile=self.owner, title="Horizon partagé",
        )
        self.other = create_project(
            actor=self.owner, owner_profile=self.owner, title="Autre horizon",
        )
        self.dossier = create_dossier(
            actor=self.owner, owner_profile=self.owner, title="Dossier secret",
        )
        link_dossier_to_project(
            actor=self.owner, project=self.project, dossier=self.dossier,
        )
        self.client = APIClient()

    def endpoint(self, name, project=None):
        return reverse(name, args=[(project or self.project).pk])

    def grant(self, profile, role_code):
        self.client.force_authenticate(user=self.owner)
        response = self.client.post(
            self.endpoint("objectives_api:project-authority"),
            {"action": "grant", "profile_id": str(profile.pk), "role_code": role_code},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        return response.data["mandate_id"]

    def test_project_viewer_sees_only_project_and_own_authority(self):
        self.grant(self.viewer, SystemRoleCode.PROJECT_VIEWER)
        self.client.force_authenticate(user=self.viewer)
        self.assertFalse(can(self.viewer, PermissionCode.PROJECT_VIEW))
        self.assertNotIn(
            PermissionCode.PROJECT_VIEW,
            effective_permission_codes(self.viewer),
        )
        self.assertFalse(
            can_many(self.viewer, [PermissionCode.PROJECT_VIEW])[
                PermissionCode.PROJECT_VIEW
            ],
        )
        self.assertTrue(can(
            self.viewer, PermissionCode.PROJECT_VIEW, project=self.project,
        ))
        self.assertTrue(
            can_many(self.viewer, [PermissionCode.PROJECT_VIEW],
                     project=self.project)[PermissionCode.PROJECT_VIEW],
        )
        self.assertFalse(can(
            self.viewer, PermissionCode.PROJECT_VIEW, project=self.other,
        ))
        detail = self.client.get(self.endpoint("objectives_api:project-detail"))
        self.assertEqual(detail.status_code, 200)
        data = detail.data["data"]
        self.assertEqual(data["visible_dossiers"], [])
        self.assertFalse(data["collaboration"]["contributors"])
        self.assertEqual(len(data["collaboration"]["members"]), 1)
        self.assertTrue(data["collaboration"]["members"][0]["self"])
        self.assertNotIn("project.edit", data["capabilities"])
        self.assertEqual(
            self.client.get(reverse(
                "objectives_api:dossier-detail", args=[self.dossier.pk],
            )).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(self.endpoint(
                "objectives_api:project-detail", self.other,
            )).status_code,
            404,
        )
        self.assertEqual(
            self.client.post(
                self.endpoint("objectives_api:project-authority"),
                {"action": "grant", "profile_id": str(self.stranger.pk),
                 "role_code": SystemRoleCode.PROJECT_VIEWER},
                format="json",
            ).status_code,
            403,
        )

    def test_project_manager_does_not_inherit_dossier_management(self):
        self.grant(self.manager, SystemRoleCode.PROJECT_MANAGER)
        self.client.force_authenticate(user=self.manager)
        data = self.client.get(
            self.endpoint("objectives_api:project-detail"),
        ).data["data"]
        self.assertIn("project.edit", data["capabilities"])
        self.assertNotIn("project.dossier.create", data["capabilities"])
        self.assertNotIn("project.authority.manage", data["capabilities"])
        self.assertEqual(
            self.client.patch(
                self.endpoint("objectives_api:project-detail"),
                {"title": "Horizon ajusté"}, format="json",
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.post(
                self.endpoint("objectives_api:project-dossiers"),
                {"action": "create", "title": "Dossier sans permission"},
                format="json",
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.get(reverse(
                "objectives_api:dossier-detail", args=[self.dossier.pk],
            )).status_code,
            404,
        )

    def test_owner_sees_real_contributors_but_no_implicit_ownership_transfer(self):
        role = Role.objects.get(
            code=SystemRoleCode.DOSSIER_MANAGER,
            scope_type=AuthorityScope.DOSSIER,
        )
        grant_dossier_role(
            profile=self.manager, dossier=self.dossier, role=role,
            granted_by=self.owner,
        )
        assign_dossier(
            actor=self.owner, dossier=self.dossier, assignee=self.manager,
        )
        self.client.force_authenticate(user=self.owner)
        data = self.client.get(
            self.endpoint("objectives_api:project-detail"),
        ).data["data"]
        contributors = data["collaboration"]["contributors"]
        self.assertEqual(len(contributors), 1)
        self.assertEqual(contributors[0]["profile_id"], str(self.manager.pk))
        self.assertEqual(contributors[0]["dossier_ids"], [str(self.dossier.pk)])
        self.assertEqual(data["collaboration"]["members"], [])
        self.client.force_authenticate(user=self.manager)
        self.assertEqual(
            self.client.get(
                self.endpoint("objectives_api:project-detail"),
            ).status_code,
            404,
        )

    def test_revoke_or_expire_project_mandate_removes_access(self):
        mandate_id = self.grant(self.viewer, SystemRoleCode.PROJECT_VIEWER)
        self.client.force_authenticate(user=self.owner)
        result = self.client.post(
            self.endpoint("objectives_api:project-authority"),
            {"action": "revoke", "mandate_id": mandate_id}, format="json",
        )
        self.assertEqual(result.status_code, 200)
        self.client.force_authenticate(user=self.viewer)
        self.assertEqual(
            self.client.get(
                self.endpoint("objectives_api:project-detail"),
            ).status_code,
            404,
        )
        role = Role.objects.get(
            code=SystemRoleCode.PROJECT_VIEWER, scope_type=AuthorityScope.PROJECT,
        )
        mandate = grant_project_role(
            profile=self.viewer, project=self.project, role=role,
        )
        mandate.valid_until = timezone.now() - timedelta(days=1)
        mandate.save(update_fields=["valid_until"])
        self.assertEqual(
            self.client.get(
                self.endpoint("objectives_api:project-detail"),
            ).status_code,
            404,
        )

    def test_cross_project_mandate_cannot_be_revoked_by_wrong_project(self):
        other_mandate = self.grant(self.viewer, SystemRoleCode.PROJECT_VIEWER)
        self.client.force_authenticate(user=self.owner)
        response = self.client.post(
            self.endpoint("objectives_api:project-authority", self.other),
            {"action": "revoke", "mandate_id": other_mandate},
            format="json",
        )
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Mandate.objects.filter(pk=other_mandate, revoked_at__isnull=True).exists())
