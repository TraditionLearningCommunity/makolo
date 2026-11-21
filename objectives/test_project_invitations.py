"""Consent-based Project invitation: pending intent must not become Mandate."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import UserProfile
from authorization.constants import PermissionCode, SystemRoleCode
from authorization.models import AuthorityScope, Mandate
from authorization.services import can
from objectives.models import ProjectInvitation, ProjectInvitationStatus
from objectives.services import create_project

User = get_user_model()


class ProjectInvitationTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="project-inviter", email="inviter@example.test",
        )
        self.guest = User.objects.create_user(
            username="project-invitee", email="guest@example.test",
            first_name="Prénom", last_name="Collaborateur",
        )
        self.other = User.objects.create_user(username="project-bystander")
        self.project = create_project(
            actor=self.owner, owner_profile=self.owner,
            title="Programme à horizon long",
        )
        self.client = APIClient()

    def invite(self, role=SystemRoleCode.PROJECT_VIEWER):
        self.client.force_authenticate(user=self.owner)
        return self.client.post(
            reverse("objectives_api:project-invite", args=[self.project.pk]),
            {"identity": self.guest.username, "role_code": role},
            format="json",
        )

    def inbox(self, user):
        self.client.force_authenticate(user=user)
        return self.client.get(reverse("objectives_api:project-invitations"))

    def respond(self, actor, invitation_id, action):
        self.client.force_authenticate(user=actor)
        return self.client.post(
            reverse("objectives_api:project-invitation-respond", args=[invitation_id]),
            {"action": action},
            format="json",
        )

    def test_pending_invitation_is_not_project_access(self):
        response = self.invite()
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["status"], "pending")
        self.assertFalse(can(self.guest, PermissionCode.PROJECT_VIEW, project=self.project))
        self.assertFalse(Mandate.objects.filter(
            scope_type=AuthorityScope.PROJECT, project=self.project,
            profile=self.guest, status="active",
        ).exists())
        self.assertEqual(self.inbox(self.other).data["results"], [])
        pending = self.inbox(self.guest)
        self.assertEqual(pending.status_code, 200)
        self.assertEqual(len(pending.data["results"]), 1)
        self.assertEqual(pending.data["results"][0]["role"], "Lecteur")
        self.client.force_authenticate(user=self.guest)
        detail = self.client.get(
            reverse("objectives_api:project-detail", args=[self.project.pk]),
        )
        self.assertEqual(detail.status_code, 404)

    def test_acceptance_creates_one_scoped_mandate_and_is_idempotently_rejected(self):
        invited = self.invite(role=SystemRoleCode.PROJECT_MANAGER)
        self.assertEqual(invited.status_code, 201)
        invitation_id = invited.data["id"]
        accepted = self.respond(self.guest, invitation_id, "accept")
        self.assertEqual(accepted.status_code, 200, accepted.data)
        self.assertEqual(accepted.data["status"], "accepted")
        self.assertTrue(can(self.guest, PermissionCode.PROJECT_VIEW, project=self.project))
        self.assertEqual(Mandate.objects.filter(
            project=self.project, profile=self.guest, status="active",
        ).count(), 1)
        self.assertEqual(self.inbox(self.guest).data["results"], [])
        self.assertEqual(
            self.respond(self.guest, invitation_id, "accept").status_code, 400,
        )

    def test_decline_grants_no_access_and_rejects_other_actor(self):
        invited = self.invite()
        self.assertEqual(invited.status_code, 201)
        ident = invited.data["id"]
        self.assertEqual(
            self.respond(self.other, ident, "accept").status_code, 404,
        )
        refused = self.respond(self.guest, ident, "decline")
        self.assertEqual(refused.status_code, 200, refused.data)
        self.assertEqual(refused.data["status"], "declined")
        self.assertFalse(can(self.guest, PermissionCode.PROJECT_VIEW, project=self.project))
        self.assertEqual(
            ProjectInvitation.objects.get(pk=ident).status,
            ProjectInvitationStatus.DECLINED,
        )

    def test_duplicate_invitation_does_not_create_new_pending_row(self):
        first = self.invite()
        second = self.invite()
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 201)
        self.assertEqual(first.data["id"], second.data["id"])
        self.assertEqual(ProjectInvitation.objects.filter(
            project=self.project, invitee=self.guest,
            status=ProjectInvitationStatus.PENDING,
        ).count(), 1)

    def test_only_manager_can_invite_and_invitation_is_project_scoped(self):
        self.client.force_authenticate(user=self.other)
        response = self.client.post(
            reverse("objectives_api:project-invite", args=[self.project.pk]),
            {"identity": self.guest.username,
             "role_code": SystemRoleCode.PROJECT_ADMIN},
            format="json",
        )
        self.assertIn(response.status_code, (403, 404))
        self.assertFalse(ProjectInvitation.objects.exists())
        invited = self.invite()
        self.assertEqual(invited.status_code, 201)
        self.client.force_authenticate(user=self.owner)
        projected = self.client.get(
            reverse("objectives_api:project-detail", args=[self.project.pk]),
        )
        self.assertEqual(projected.status_code, 200)
        self.assertEqual(
            len(projected.data["data"]["collaboration"]["pending_invitations"]), 1,
        )

    def test_search_never_exposes_partial_email_or_non_searchable_profile(self):
        profile, _ = UserProfile.objects.get_or_create(user=self.guest)
        profile.searchable = False
        profile.save(update_fields=["searchable"])
        self.client.force_authenticate(user=self.owner)
        url = reverse("objectives_api:project-people-search", args=[self.project.pk])
        hidden = self.client.get(url, {"q": "Prénom"})
        self.assertEqual(hidden.status_code, 200)
        self.assertEqual(hidden.data["results"], [])
        exact = self.client.get(url, {"q": self.guest.email})
        self.assertEqual(exact.status_code, 200)
        self.assertEqual(len(exact.data["results"]), 1)
        self.assertEqual(exact.data["results"][0]["email"], self.guest.email)
        profile.searchable = True
        profile.save(update_fields=["searchable"])
        public = self.client.get(url, {"q": "Prénom"})
        self.assertEqual(public.status_code, 200)
        self.assertEqual(len(public.data["results"]), 1)
        self.assertIsNone(public.data["results"][0]["email"])

    def test_web_invitation_requires_consent_and_is_found_from_mesas_demarches(self):
        from authorization.models import Role
        role = Role.objects.get(
            code=SystemRoleCode.PROJECT_VIEWER,
            scope_type=AuthorityScope.PROJECT,
        )
        self.client.force_authenticate(user=None)
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("objectives:project-authority", args=[self.project.pk]),
            {
                "action": "invite",
                "identity": self.guest.username,
                "role": str(role.pk),
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(can(
            self.guest, PermissionCode.PROJECT_VIEW, project=self.project,
        ))
        invitation = ProjectInvitation.objects.get(
            project=self.project, invitee=self.guest,
            status=ProjectInvitationStatus.PENDING,
        )
        self.client.force_login(self.guest)
        inbox = self.client.get(reverse("objectives:project-invitations"))
        self.assertEqual(inbox.status_code, 200)
        self.assertContains(inbox, self.project.title)
        self.assertContains(inbox, "Accepter")
        self.assertContains(inbox, "Décliner")
        accepted = self.client.post(
            reverse("objectives:project-invitation-respond", args=[invitation.pk]),
            {"action": "accept"},
        )
        self.assertEqual(accepted.status_code, 302)
        self.assertTrue(can(
            self.guest, PermissionCode.PROJECT_VIEW, project=self.project,
        ))

    def test_cancelled_invitation_cannot_be_accepted(self):
        invited = self.invite()
        self.assertEqual(invited.status_code, 201)
        ident = invited.data["id"]
        self.client.force_authenticate(user=self.owner)
        cancelled = self.client.post(
            reverse("objectives_api:project-invitation-cancel", args=[ident]),
            {}, format="json",
        )
        self.assertEqual(cancelled.status_code, 200)
        self.assertEqual(cancelled.data["status"], "cancelled")
        self.assertEqual(
            self.respond(self.guest, ident, "accept").status_code, 400,
        )
        self.assertFalse(can(self.guest, PermissionCode.PROJECT_VIEW, project=self.project))
