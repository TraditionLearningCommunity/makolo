from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from authorization.constants import SystemRoleCode
from authorization.platform_services import grant_platform_role
from authorization.services import grant_space_role
from organizations.models import Organization

from .models import Dossier, Project, ProjectDossierLink, ProjectLifecycle
from .selectors import visible_dossiers_for_project, visible_project_for_dossier
from .services import create_dossier, create_project, link_dossier_to_project, move_dossier_to_project, set_project_lifecycle, unlink_dossier_from_project


User = get_user_model()


class D5ProjectTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(username="d5-alice", email="d5-alice@example.test", password="StrongPass2026!")
        self.bob = User.objects.create_user(username="d5-bob", email="d5-bob@example.test", password="StrongPass2026!")
        self.platform = User.objects.create_user(username="d5-platform", email="d5-platform@example.test", password="StrongPass2026!")
        grant_platform_role(profile=self.platform, role=SystemRoleCode.PLATFORM_ADMIN, granted_by=self.platform)

    def test_project_foundation_owner_xor_horizon_and_space_authority(self):
        personal = create_project(actor=self.alice, owner_profile=self.alice, title="Études universitaires")
        self.assertEqual(personal.owner_profile, self.alice)
        self.assertIsNone(personal.owning_space_id)
        with self.assertRaises(ValidationError):
            Project.objects.create(title="Invalide", created_by=self.alice, owner_profile=self.alice, owning_space=Organization.objects.create(name="X", created_by=self.alice))
        with self.assertRaises(ValidationError):
            create_project(actor=self.alice, owner_profile=self.alice, title="Horizon", starts_on="2026-10-02", ends_on="2026-10-01")
        space = Organization.objects.create(name="Espace D5", created_by=self.alice)
        with self.assertRaises(PermissionDenied):
            create_project(actor=self.bob, owning_space=space, title="Interdit")
        grant_space_role(profile=self.alice, space=space, role=SystemRoleCode.SPACE_ADMIN, granted_by=self.alice)
        project = create_project(actor=self.alice, owning_space=space, title="Projet Espace")
        self.assertEqual(project.owning_space, space)

    def test_link_enforces_one_active_project_and_unlink_keeps_dossier(self):
        dossier = create_dossier(actor=self.alice, owner_profile=self.alice, title="Obtenir la bourse")
        project_a = create_project(actor=self.alice, owner_profile=self.alice, title="Projet A")
        project_b = create_project(actor=self.alice, owner_profile=self.alice, title="Projet B")
        link = link_dossier_to_project(actor=self.alice, project=project_a, dossier=dossier)
        self.assertEqual(link_dossier_to_project(actor=self.alice, project=project_a, dossier=dossier).pk, link.pk)
        with self.assertRaises(ValidationError): link_dossier_to_project(actor=self.alice, project=project_b, dossier=dossier)
        with self.assertRaises(IntegrityError):
            with transaction.atomic(): ProjectDossierLink.objects.create(project=project_b, dossier=dossier, linked_by=self.alice)
        unlink_dossier_from_project(actor=self.alice, project=project_a, dossier=dossier)
        link.refresh_from_db(); dossier.refresh_from_db()
        self.assertFalse(link.is_active); self.assertIsNotNone(link.removed_at); self.assertTrue(Dossier.objects.filter(pk=dossier.pk).exists())

    def test_move_is_historized_and_leaves_one_active_link(self):
        dossier = create_dossier(actor=self.alice, owner_profile=self.alice, title="Inscription")
        project_a = create_project(actor=self.alice, owner_profile=self.alice, title="A")
        project_b = create_project(actor=self.alice, owner_profile=self.alice, title="B")
        old = link_dossier_to_project(actor=self.alice, project=project_a, dossier=dossier)
        new = move_dossier_to_project(actor=self.alice, dossier=dossier, target_project=project_b)
        old.refresh_from_db()
        self.assertFalse(old.is_active); self.assertEqual(old.removed_by, self.alice)
        self.assertTrue(new.is_active); self.assertEqual(new.project, project_b)
        self.assertEqual(ProjectDossierLink.objects.filter(dossier=dossier, is_active=True).count(), 1)
        self.assertEqual(ProjectDossierLink.objects.filter(dossier=dossier).count(), 2)

    def test_link_requires_authority_on_project_and_dossier_cross_space(self):
        space_a = Organization.objects.create(name="A", created_by=self.alice); space_b = Organization.objects.create(name="B", created_by=self.bob)
        grant_space_role(profile=self.alice, space=space_a, role=SystemRoleCode.SPACE_ADMIN, granted_by=self.alice)
        grant_space_role(profile=self.bob, space=space_b, role=SystemRoleCode.SPACE_ADMIN, granted_by=self.bob)
        project = create_project(actor=self.alice, owning_space=space_a, title="Projet A")
        dossier = create_dossier(actor=self.bob, owning_space=space_b, title="Dossier B")
        with self.assertRaises(PermissionDenied): link_dossier_to_project(actor=self.alice, project=project, dossier=dossier)
        with self.assertRaises(PermissionDenied): link_dossier_to_project(actor=self.bob, project=project, dossier=dossier)
        grant_space_role(profile=self.alice, space=space_b, role=SystemRoleCode.SPACE_ADMIN, granted_by=self.bob)
        link = link_dossier_to_project(actor=self.alice, project=project, dossier=dossier)
        self.assertTrue(link.is_active)

    def test_project_and_dossier_visibility_remain_independent(self):
        project = create_project(actor=self.alice, owner_profile=self.alice, title="Projet visible")
        visible = create_dossier(actor=self.alice, owner_profile=self.alice, title="Visible")
        hidden = create_dossier(actor=self.bob, owner_profile=self.bob, title="Dossier secret")
        link_dossier_to_project(actor=self.platform, project=project, dossier=visible)
        link_dossier_to_project(actor=self.platform, project=project, dossier=hidden)
        self.assertEqual(list(visible_dossiers_for_project(self.alice, project).values_list("pk", flat=True)), [visible.pk])
        self.assertIsNone(visible_project_for_dossier(self.bob, hidden))
        self.client.force_login(self.alice)
        response = self.client.get(reverse("objectives:project-detail", args=[project.pk]))
        self.assertContains(response, "Visible"); self.assertNotContains(response, "Dossier secret"); self.assertContains(response, "1 dossier visible")
        self.client.force_login(self.bob)
        response = self.client.get(reverse("objectives:dossier-detail", args=[hidden.pk]))
        self.assertNotContains(response, "Projet visible")

    def test_project_lifecycle_does_not_propagate_and_non_operational_project_rejects_new_link(self):
        dossier = create_dossier(actor=self.alice, owner_profile=self.alice, title="Logement")
        project = create_project(actor=self.alice, owner_profile=self.alice, title="Projet")
        original = dossier.lifecycle
        set_project_lifecycle(actor=self.alice, project=project, lifecycle=ProjectLifecycle.ARCHIVED)
        dossier.refresh_from_db(); self.assertEqual(dossier.lifecycle, original)
        other = create_dossier(actor=self.alice, owner_profile=self.alice, title="Autre")
        with self.assertRaises(ValidationError): link_dossier_to_project(actor=self.alice, project=project, dossier=other)

    def test_dossier_without_project_remains_valid(self):
        dossier = create_dossier(actor=self.alice, owner_profile=self.alice, title="Sans projet")
        self.assertFalse(ProjectDossierLink.objects.filter(dossier=dossier, is_active=True).exists())
        self.client.force_login(self.alice)
        self.assertEqual(self.client.get(reverse("objectives:dossier-detail", args=[dossier.pk])).status_code, 200)

    @patch("objectives.services.emit_domain_event")
    def test_project_events_use_minimal_payloads(self, emit):
        project = create_project(actor=self.alice, owner_profile=self.alice, title="Projet")
        dossier = create_dossier(actor=self.alice, owner_profile=self.alice, title="Dossier")
        link_dossier_to_project(actor=self.alice, project=project, dossier=dossier)
        payloads = [call.kwargs["payload"] for call in emit.call_args_list]
        self.assertIn({"project_id": str(project.pk)}, payloads)
        link_payload = next(payload for payload in payloads if payload.get("project_id") == str(project.pk) and payload.get("dossier_id") == str(dossier.pk))
        self.assertEqual(set(link_payload), {"project_id", "dossier_id", "link_id"})
        for payload in payloads:
            self.assertNotIn("title", payload); self.assertNotIn("description", payload); self.assertNotIn("readiness", payload)
