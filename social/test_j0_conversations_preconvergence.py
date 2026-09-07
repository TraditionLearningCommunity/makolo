from django.contrib.auth import get_user_model
from django.test import TestCase

from accounts.models import UserProfile
from activities.involvement_services import create_external_involvement
from activities.models import Activity
from authorization.constants import PermissionCode
from authorization.models import AuthorityScope, Permission, Role, RolePermission
from authorization.services import can, grant_space_role
from domain_events.contracts import DomainEventType
from domain_events.models import DomainEventOutbox
from organizations.models import Organization
from topics.models import ActionMatchKind, ProfileOpenTo

from .bilateral_services import (
    create_action_need,
    create_action_proposal,
    respond_to_action_proposal,
    transition_action_need,
)
from .models import (
    ActionNeedStatus,
    ActionNeedVisibility,
    ActionNeedIntakePolicy,
    ActionProposalDirection,
    ActionProposalStatus,
)
from .profile_search import action_proposals_requiring_actor_response


User = get_user_model()
PASSWORD = "Strong-J0-Password-2026!"


def make_user(username):
    user = User.objects.create_user(
        username=username,
        email=f"{username}@example.test",
        password=PASSWORD,
    )
    UserProfile.objects.create(user=user, public_profile=True, searchable=True)
    return user


def grant_fine_space_action_network_manage(*, actor, space):
    permission = Permission.objects.get(code=PermissionCode.SPACE_ACTION_NETWORK_MANAGE)
    role = Role.objects.create(
        code=f"j0-action-network-{actor.username}",
        name="Gestion réseau d'action J0",
        scope_type=AuthorityScope.SPACE,
        organization=space,
        is_system=False,
        is_active=True,
    )
    RolePermission.objects.create(role=role, permission=permission)
    return grant_space_role(profile=actor, space=space, role=role, granted_by=actor, source="j0-test")


class J0FineActionNetworkAuthorityTests(TestCase):
    def setUp(self):
        self.manager = make_user("j0-fine-manager")
        self.outsider = make_user("j0-fine-outsider")
        self.space = Organization.objects.create(name="J0 Fine Space", created_by=self.manager)
        self.activity = Activity.objects.create(space=self.space, created_by=self.manager, title="J0 Fine Activity")
        grant_fine_space_action_network_manage(actor=self.manager, space=self.space)

    def test_space_fine_permission_inherits_into_activity_action_network(self):
        self.assertTrue(can(self.manager, PermissionCode.SPACE_ACTION_NETWORK_MANAGE, space=self.space))
        self.assertTrue(can(self.manager, PermissionCode.ACTIVITY_ACTION_NETWORK_MANAGE, activity=self.activity))
        self.assertFalse(can(self.manager, PermissionCode.ACTIVITY_MANAGE, activity=self.activity))

    def test_fine_permission_can_create_activity_need_without_activity_manage(self):
        need = create_action_need(
            actor=self.manager,
            space=self.space,
            activity=self.activity,
            title="Intervenant J0",
            match_kind=ActionMatchKind.SPEAK,
        )
        self.assertEqual(need.activity, self.activity)
        self.assertFalse(can(self.manager, PermissionCode.ACTIVITY_MANAGE, activity=self.activity))

    def test_fine_permission_can_manage_activity_involvement_without_activity_manage(self):
        involvement = create_external_involvement(
            actor=self.manager,
            activity=self.activity,
            external_display_name="Invité J0",
        )
        self.assertEqual(involvement.activity, self.activity)
        self.assertFalse(can(self.manager, PermissionCode.ACTIVITY_MANAGE, activity=self.activity))

    def test_outsider_still_cannot_manage_activity_action_network(self):
        self.assertFalse(can(self.outsider, PermissionCode.ACTIVITY_ACTION_NETWORK_MANAGE, activity=self.activity))


class J0ActionNetworkDomainEventTests(TestCase):
    def setUp(self):
        self.owner = make_user("j0-event-owner")
        self.candidate = make_user("j0-event-candidate")
        ProfileOpenTo.objects.create(
            profile=self.candidate,
            kind=ActionMatchKind.MENTOR,
            is_active=True,
            is_searchable=True,
        )

    def test_need_and_proposal_lifecycle_emit_material_domain_events(self):
        need = create_action_need(
            actor=self.owner,
            owner_profile=self.owner,
            title="Mentorat J0",
            match_kind=ActionMatchKind.MENTOR,
        )
        self.assertTrue(
            DomainEventOutbox.objects.filter(
                event_type=DomainEventType.ACTION_NEED_OPENED,
                source_id=str(need.pk),
            ).exists()
        )

        proposal = create_action_proposal(
            actor=self.owner,
            need=need,
            candidate_profile=self.candidate,
        )
        self.assertTrue(
            DomainEventOutbox.objects.filter(
                event_type=DomainEventType.ACTION_PROPOSAL_CREATED,
                source_id=str(proposal.pk),
            ).exists()
        )

        respond_to_action_proposal(
            actor=self.candidate,
            proposal=proposal,
            status=ActionProposalStatus.ACCEPTED,
        )
        self.assertTrue(
            DomainEventOutbox.objects.filter(
                event_type=DomainEventType.ACTION_PROPOSAL_ACCEPTED,
                source_id=str(proposal.pk),
            ).exists()
        )

        transition_action_need(actor=self.owner, need=need, status=ActionNeedStatus.FILLED)
        self.assertTrue(
            DomainEventOutbox.objects.filter(
                event_type=DomainEventType.ACTION_NEED_FILLED,
                source_id=str(need.pk),
            ).exists()
        )

    def test_domain_event_payload_does_not_copy_free_text(self):
        need = create_action_need(
            actor=self.owner,
            owner_profile=self.owner,
            title="Titre sensible non nécessaire à l'événement",
            description="Description libre qui ne doit pas entrer dans le bus.",
            match_kind=ActionMatchKind.MENTOR,
        )
        event = DomainEventOutbox.objects.get(
            event_type=DomainEventType.ACTION_NEED_OPENED,
            source_id=str(need.pk),
        )
        serialized = str(event.payload)
        self.assertNotIn(need.title, serialized)
        self.assertNotIn(need.description, serialized)


class J0CanonicalActionInboxTests(TestCase):
    def setUp(self):
        self.owner = make_user("j0-inbox-owner")
        self.candidate = make_user("j0-inbox-candidate")
        self.other = make_user("j0-inbox-other")
        ProfileOpenTo.objects.create(
            profile=self.candidate,
            kind=ActionMatchKind.COLLABORATE,
            is_active=True,
            is_searchable=True,
        )

    def ids_for(self, actor):
        return set(action_proposals_requiring_actor_response(actor).values_list("id", flat=True))

    def test_profile_invitation_is_in_candidate_inbox_only_while_pending(self):
        need = create_action_need(
            actor=self.owner,
            owner_profile=self.owner,
            title="Collaboration J0",
            match_kind=ActionMatchKind.COLLABORATE,
        )
        proposal = create_action_proposal(
            actor=self.owner,
            need=need,
            candidate_profile=self.candidate,
        )
        self.assertIn(proposal.pk, self.ids_for(self.candidate))
        self.assertNotIn(proposal.pk, self.ids_for(self.other))

        respond_to_action_proposal(
            actor=self.candidate,
            proposal=proposal,
            status=ActionProposalStatus.DECLINED,
        )
        self.assertNotIn(proposal.pk, self.ids_for(self.candidate))

    def test_candidate_initiated_proposal_is_in_personal_owner_inbox(self):
        need = create_action_need(
            actor=self.owner,
            owner_profile=self.owner,
            title="Besoin ouvert J0",
            match_kind=ActionMatchKind.COLLABORATE,
            visibility=ActionNeedVisibility.PUBLIC,
            intake_policy=ActionNeedIntakePolicy.OPEN,
        )
        proposal = create_action_proposal(
            actor=self.candidate,
            need=need,
            candidate_profile=self.candidate,
            direction=ActionProposalDirection.CANDIDATE_TO_OWNER,
            client_reference="j0-personal-owner",
        )
        self.assertIn(proposal.pk, self.ids_for(self.owner))
        self.assertNotIn(proposal.pk, self.ids_for(self.other))

    def test_space_authority_receives_space_candidate_and_space_owner_proposals(self):
        manager = make_user("j0-inbox-space-manager")
        space = Organization.objects.create(name="J0 Inbox Space", created_by=manager)
        grant_fine_space_action_network_manage(actor=manager, space=space)

        candidate_need = create_action_need(
            actor=self.owner,
            owner_profile=self.owner,
            title="Space candidate J0",
            match_kind=ActionMatchKind.PARTNER,
            candidate_kind="space",
        )
        from topics.models import SpaceOpenTo
        SpaceOpenTo.objects.create(
            space=space,
            kind=ActionMatchKind.PARTNER,
            is_active=True,
            is_searchable=True,
        )
        incoming = create_action_proposal(
            actor=self.owner,
            need=candidate_need,
            candidate_space=space,
        )

        owned_need = create_action_need(
            actor=manager,
            space=space,
            title="Space owner J0",
            match_kind=ActionMatchKind.COLLABORATE,
            visibility=ActionNeedVisibility.PUBLIC,
            intake_policy=ActionNeedIntakePolicy.OPEN,
        )
        outgoing_candidate = create_action_proposal(
            actor=self.candidate,
            need=owned_need,
            candidate_profile=self.candidate,
            direction=ActionProposalDirection.CANDIDATE_TO_OWNER,
            client_reference="j0-space-owner",
        )

        manager_ids = self.ids_for(manager)
        self.assertIn(incoming.pk, manager_ids)
        self.assertIn(outgoing_candidate.pk, manager_ids)
        self.assertNotIn(incoming.pk, self.ids_for(self.other))
        self.assertNotIn(outgoing_candidate.pk, self.ids_for(self.other))