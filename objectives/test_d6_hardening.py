from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.test import TestCase
from django.urls import reverse

from authorization.constants import SystemRoleCode
from authorization.services import grant_space_role
from domain_events.contracts import DomainEventType
from organizations.models import Organization

from .models import ProjectDossierLink, ProjectLifecycle
from .services import (
    create_dossier,
    create_project,
    link_dossier_to_project,
    move_dossier_to_project,
    set_project_lifecycle,
    unlink_dossier_from_project,
)


User = get_user_model()


class D6ProjectHardeningTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(
            username="d6-alice",
            email="d6-alice@example.test",
            password="StrongPass2026!",
        )
        self.bob = User.objects.create_user(
            username="d6-bob",
            email="d6-bob@example.test",
            password="StrongPass2026!",
        )

    def test_unauthorized_lifecycle_change_is_rejected_and_unchanged(self):
        project = create_project(actor=self.alice, owner_profile=self.alice, title="Projet privé")

        with self.assertRaises(PermissionDenied):
            set_project_lifecycle(actor=self.bob, project=project, lifecycle=ProjectLifecycle.ACTIVE)

        project.refresh_from_db()
        self.assertEqual(project.lifecycle, ProjectLifecycle.DRAFT)

    def test_unauthorized_unlink_is_rejected_and_link_remains_active(self):
        project = create_project(actor=self.alice, owner_profile=self.alice, title="Projet")
        dossier = create_dossier(actor=self.alice, owner_profile=self.alice, title="Dossier")
        link = link_dossier_to_project(actor=self.alice, project=project, dossier=dossier)

        with self.assertRaises(PermissionDenied):
            unlink_dossier_from_project(actor=self.bob, project=project, dossier=dossier)

        link.refresh_from_db()
        self.assertTrue(link.is_active)
        self.assertIsNone(link.removed_at)
        self.assertIsNone(link.removed_by_id)

    def test_move_requires_authority_on_target_project(self):
        source = create_project(actor=self.alice, owner_profile=self.alice, title="Source")
        target = create_project(actor=self.bob, owner_profile=self.bob, title="Target")
        dossier = create_dossier(actor=self.alice, owner_profile=self.alice, title="Dossier")
        old_link = link_dossier_to_project(actor=self.alice, project=source, dossier=dossier)

        with self.assertRaises(PermissionDenied):
            move_dossier_to_project(actor=self.alice, dossier=dossier, target_project=target)

        old_link.refresh_from_db()
        self.assertTrue(old_link.is_active)
        self.assertEqual(
            ProjectDossierLink.objects.filter(dossier=dossier, is_active=True).count(),
            1,
        )

    def test_move_requires_authority_on_source_project(self):
        source_space = Organization.objects.create(name="D6 Source Space", created_by=self.bob)
        target_space = Organization.objects.create(name="D6 Target Space", created_by=self.alice)
        grant_space_role(
            profile=self.bob,
            space=source_space,
            role=SystemRoleCode.SPACE_ADMIN,
            granted_by=self.bob,
        )
        grant_space_role(
            profile=self.alice,
            space=target_space,
            role=SystemRoleCode.SPACE_ADMIN,
            granted_by=self.alice,
        )
        source = create_project(actor=self.bob, owning_space=source_space, title="Source")
        target = create_project(actor=self.alice, owning_space=target_space, title="Target")
        dossier = create_dossier(actor=self.bob, owning_space=source_space, title="Dossier")
        old_link = link_dossier_to_project(actor=self.bob, project=source, dossier=dossier)
        grant_space_role(
            profile=self.alice,
            space=source_space,
            role=SystemRoleCode.SPACE_ADMIN,
            granted_by=self.bob,
        )

        # Alice can now manage the Dossier and target, but not the source Project
        # would be false if source authority came only from the same Space. Revoke
        # that ambiguity by using a personal source Project instead.
        personal_source = create_project(actor=self.bob, owner_profile=self.bob, title="Personal Source")
        unlink_dossier_from_project(actor=self.bob, project=source, dossier=dossier)
        old_link = link_dossier_to_project(actor=self.bob, project=personal_source, dossier=dossier)

        with self.assertRaises(PermissionDenied):
            move_dossier_to_project(actor=self.alice, dossier=dossier, target_project=target)

        old_link.refresh_from_db()
        self.assertTrue(old_link.is_active)
        self.assertEqual(old_link.project, personal_source)

    def test_direct_uuid_and_post_do_not_bypass_project_authority(self):
        project = create_project(actor=self.alice, owner_profile=self.alice, title="Projet privé")
        dossier = create_dossier(actor=self.alice, owner_profile=self.alice, title="Dossier privé")
        link_dossier_to_project(actor=self.alice, project=project, dossier=dossier)
        self.client.force_login(self.bob)

        self.assertEqual(
            self.client.get(reverse("objectives:project-detail", args=[project.pk])).status_code,
            404,
        )
        self.assertEqual(
            self.client.post(
                reverse("objectives:project-lifecycle", args=[project.pk]),
                {"lifecycle": ProjectLifecycle.ACTIVE},
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.post(
                reverse("objectives:project-unlink-dossier", args=[project.pk, dossier.pk]),
            ).status_code,
            404,
        )

    @patch("objectives.services.emit_domain_event")
    def test_project_mutation_events_have_exact_minimal_payloads(self, emit):
        source = create_project(actor=self.alice, owner_profile=self.alice, title="Source")
        target = create_project(actor=self.alice, owner_profile=self.alice, title="Target")
        dossier = create_dossier(actor=self.alice, owner_profile=self.alice, title="Dossier")
        link_dossier_to_project(actor=self.alice, project=source, dossier=dossier)
        emit.reset_mock()

        set_project_lifecycle(actor=self.alice, project=source, lifecycle=ProjectLifecycle.ACTIVE)
        lifecycle_call = emit.call_args
        self.assertEqual(lifecycle_call.kwargs["event_type"], DomainEventType.PROJECT_LIFECYCLE_CHANGED)
        self.assertEqual(
            lifecycle_call.kwargs["payload"],
            {
                "project_id": str(source.pk),
                "previous": ProjectLifecycle.DRAFT,
                "current": ProjectLifecycle.ACTIVE,
            },
        )

        emit.reset_mock()
        moved_link = move_dossier_to_project(actor=self.alice, dossier=dossier, target_project=target)
        self.assertEqual(emit.call_count, 1)
        move_call = emit.call_args
        self.assertEqual(move_call.kwargs["event_type"], DomainEventType.PROJECT_DOSSIER_MOVED)
        self.assertEqual(
            move_call.kwargs["payload"],
            {
                "dossier_id": str(dossier.pk),
                "source_project_id": str(source.pk),
                "target_project_id": str(target.pk),
            },
        )

        emit.reset_mock()
        unlink_dossier_from_project(actor=self.alice, project=target, dossier=dossier)
        self.assertEqual(emit.call_count, 1)
        unlink_call = emit.call_args
        self.assertEqual(unlink_call.kwargs["event_type"], DomainEventType.PROJECT_DOSSIER_UNLINKED)
        self.assertEqual(
            unlink_call.kwargs["payload"],
            {
                "project_id": str(target.pk),
                "dossier_id": str(dossier.pk),
                "link_id": str(moved_link.pk),
            },
        )
        forbidden_keys = {
            "title",
            "description",
            "beneficiary",
            "readiness",
            "journey",
            "assignment",
            "mandate",
        }
        for call in (lifecycle_call, move_call, unlink_call):
            self.assertTrue(forbidden_keys.isdisjoint(call.kwargs["payload"]))

    def test_move_rolls_back_link_history_if_event_write_fails(self):
        source = create_project(actor=self.alice, owner_profile=self.alice, title="Source")
        target = create_project(actor=self.alice, owner_profile=self.alice, title="Target")
        dossier = create_dossier(actor=self.alice, owner_profile=self.alice, title="Dossier")
        old_link = link_dossier_to_project(actor=self.alice, project=source, dossier=dossier)

        with patch(
            "objectives.services.emit_domain_event",
            side_effect=RuntimeError("event failure"),
        ):
            with self.assertRaises(RuntimeError):
                move_dossier_to_project(actor=self.alice, dossier=dossier, target_project=target)

        old_link.refresh_from_db()
        self.assertTrue(old_link.is_active)
        self.assertIsNone(old_link.removed_at)
        self.assertIsNone(old_link.removed_by_id)
        self.assertEqual(
            ProjectDossierLink.objects.filter(dossier=dossier, is_active=True).count(),
            1,
        )
        self.assertFalse(
            ProjectDossierLink.objects.filter(dossier=dossier, project=target).exists()
        )
