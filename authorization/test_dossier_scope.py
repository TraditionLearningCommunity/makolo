from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from activities.models import Activity
from objectives.models import Dossier

from .constants import PermissionCode, SystemRoleCode
from .models import AuthorityScope, Mandate
from .services import can, get_system_role, grant_activity_role, grant_dossier_role


User = get_user_model()


class DossierAuthorityScopeTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="d3-auth-owner", email="d3-auth-owner@example.test", password="StrongPass2026!")
        self.collaborator = User.objects.create_user(username="d3-auth-collab", email="d3-auth-collab@example.test", password="StrongPass2026!")
        self.dossier = Dossier.objects.create(title="Dossier A", created_by=self.owner, owner_profile=self.owner)
        self.other_dossier = Dossier.objects.create(title="Dossier B", created_by=self.owner, owner_profile=self.owner)
        self.activity = Activity.objects.create(owner_profile=self.owner, created_by=self.owner, title="Activity D3")

    def test_dossier_mandate_is_local_and_contains_only_role_permissions(self):
        grant_dossier_role(profile=self.collaborator, dossier=self.dossier, role=SystemRoleCode.DOSSIER_VIEWER, granted_by=self.owner)
        self.assertTrue(can(self.collaborator, PermissionCode.DOSSIER_VIEW, dossier=self.dossier))
        self.assertFalse(can(self.collaborator, PermissionCode.DOSSIER_MANAGE, dossier=self.dossier))
        self.assertFalse(can(self.collaborator, PermissionCode.DOSSIER_VIEW, dossier=self.other_dossier))
        self.assertFalse(can(self.collaborator, PermissionCode.ACTIVITY_VIEW, activity=self.activity))

    def test_existing_activity_scope_still_resolves(self):
        grant_activity_role(profile=self.collaborator, activity=self.activity, granted_by=self.owner)
        self.assertTrue(can(self.collaborator, PermissionCode.ACTIVITY_MANAGE, activity=self.activity))
        self.assertFalse(can(self.collaborator, PermissionCode.DOSSIER_MANAGE, dossier=self.dossier))

    def test_dossier_scope_rejects_an_extra_scope_target(self):
        role = get_system_role(SystemRoleCode.DOSSIER_MANAGER, scope_type=AuthorityScope.DOSSIER)
        mandate = Mandate(profile=self.collaborator, role=role, scope_type=AuthorityScope.DOSSIER, dossier=self.dossier, activity=self.activity)
        with self.assertRaises(ValidationError): mandate.full_clean()
