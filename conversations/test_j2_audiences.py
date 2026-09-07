from django.contrib.auth import get_user_model
from django.test import TestCase

from activities.involvement_models import (
    ActivityInvolvement,
    ActivityInvolvementConfirmationBasis,
    ActivityInvolvementFunction,
    ActivityInvolvementFunctionKind,
)
from activities.models import Activity
from authorization.constants import SystemRoleCode
from authorization.services import grant_activity_role
from groups.models import Group, GroupMembership, GroupMembershipSource, GroupMembershipStatus
from organizations.models import Organization

from .audience_models import ConversationAudienceRuleKind, ConversationAudienceRuleOperation
from .audience_services import add_audience_rule, create_audience_set, profile_in_audience, resolve_audience_ids
from .core_models import ConversationContextKind
from .services import can_manage_conversation, ensure_context_conversation


User = get_user_model()


class ConversationAudienceTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="j2-owner", email="j2-owner@example.test", password="StrongPass2026!")
        self.communicator = User.objects.create_user(username="j2-comms", email="j2-comms@example.test", password="StrongPass2026!")
        self.member = User.objects.create_user(username="j2-member", email="j2-member@example.test", password="StrongPass2026!")
        self.other = User.objects.create_user(username="j2-other", email="j2-other@example.test", password="StrongPass2026!")
        self.space = Organization.objects.create(name="J2 Space", created_by=self.owner)
        self.activity = Activity.objects.create(space=self.space, created_by=self.owner, title="J2 Activity")
        grant_activity_role(
            profile=self.communicator,
            activity=self.activity,
            role_code=SystemRoleCode.ACTIVITY_COMMUNICATION_MANAGER,
            granted_by=self.owner,
            source="j2-test",
        )
        self.activity_conversation = ensure_context_conversation(
            actor=self.communicator,
            kind=ConversationContextKind.ACTIVITY,
            activity=self.activity,
        )

    def test_function_audience_is_derived_from_live_activity_involvement(self):
        involvement = ActivityInvolvement.objects.create(
            activity=self.activity,
            profile=self.member,
            confirmation_basis=ActivityInvolvementConfirmationBasis.PROFILE_CONFIRMED,
            recorded_by=self.owner,
            confirmed_by=self.member,
        )
        ActivityInvolvementFunction.objects.create(
            involvement=involvement,
            kind=ActivityInvolvementFunctionKind.SPEAKER,
            label="Intervenant",
        )
        audience = create_audience_set(actor=self.communicator, conversation=self.activity_conversation, label="Intervenants")
        add_audience_rule(
            actor=self.communicator,
            audience_set=audience,
            operation=ConversationAudienceRuleOperation.INCLUDE,
            kind=ConversationAudienceRuleKind.ACTIVITY_INVOLVEMENT_FUNCTION,
            activity=self.activity,
            involvement_function_kind=ActivityInvolvementFunctionKind.SPEAKER,
        )
        self.assertTrue(profile_in_audience(self.member, audience))
        self.assertFalse(profile_in_audience(self.other, audience))

    def test_group_membership_is_dynamic_and_does_not_grant_management(self):
        group = Group.objects.create(name="J2 Groupe", owner_profile=self.owner, created_by=self.owner)
        membership = GroupMembership.objects.create(
            group=group,
            profile=self.member,
            status=GroupMembershipStatus.ACTIVE,
            source=GroupMembershipSource.MANUAL,
        )
        conversation = ensure_context_conversation(actor=self.owner, kind=ConversationContextKind.GROUP, group=group)
        audience = create_audience_set(actor=self.owner, conversation=conversation, label="Membres")
        add_audience_rule(
            actor=self.owner,
            audience_set=audience,
            operation=ConversationAudienceRuleOperation.INCLUDE,
            kind=ConversationAudienceRuleKind.GROUP_MEMBERS,
            group=group,
        )
        self.assertTrue(profile_in_audience(self.member, audience))
        self.assertFalse(can_manage_conversation(self.member, conversation))
        membership.status = GroupMembershipStatus.REMOVED
        membership.save(update_fields=["status", "updated_at"])
        self.assertFalse(profile_in_audience(self.member, audience))

    def test_exclude_rule_wins_after_union_and_cannot_expand_base_access(self):
        involvement = ActivityInvolvement.objects.create(
            activity=self.activity,
            profile=self.member,
            confirmation_basis=ActivityInvolvementConfirmationBasis.PROFILE_CONFIRMED,
            recorded_by=self.owner,
            confirmed_by=self.member,
        )
        ActivityInvolvementFunction.objects.create(involvement=involvement, kind=ActivityInvolvementFunctionKind.SPEAKER)
        audience = create_audience_set(actor=self.communicator, conversation=self.activity_conversation, label="Sélection")
        add_audience_rule(
            actor=self.communicator,
            audience_set=audience,
            operation=ConversationAudienceRuleOperation.INCLUDE,
            kind=ConversationAudienceRuleKind.ALL_CONVERSATION_VIEWERS,
        )
        add_audience_rule(
            actor=self.communicator,
            audience_set=audience,
            operation=ConversationAudienceRuleOperation.EXCLUDE,
            kind=ConversationAudienceRuleKind.EXPLICIT_PROFILE,
            profile=self.member,
        )
        add_audience_rule(
            actor=self.communicator,
            audience_set=audience,
            operation=ConversationAudienceRuleOperation.INCLUDE,
            kind=ConversationAudienceRuleKind.EXPLICIT_PROFILE,
            profile=self.other,
        )
        ids = resolve_audience_ids(audience)
        self.assertNotIn(self.member.pk, ids)
        self.assertNotIn(self.other.pk, ids)
        self.assertIn(self.communicator.pk, ids)
