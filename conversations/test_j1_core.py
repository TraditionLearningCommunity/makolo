from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase

from activities.models import Activity
from authorization.constants import PermissionCode, SystemRoleCode
from authorization.services import can, grant_activity_role
from organizations.models import Organization

from .models import ConversationContextKind, ConversationLifecycle, ConversationModePreset
from .services import (
    can_manage_conversation,
    ensure_context_conversation,
    set_conversation_policy,
    transition_conversation,
)


User = get_user_model()


class ConversationCoreTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="j1-owner", email="j1-owner@example.test", password="StrongPass2026!")
        self.communicator = User.objects.create_user(username="j1-communicator", email="j1-communicator@example.test", password="StrongPass2026!")
        self.outsider = User.objects.create_user(username="j1-outsider", email="j1-outsider@example.test", password="StrongPass2026!")
        self.space = Organization.objects.create(name="J1 Space", created_by=self.owner)
        self.activity = Activity.objects.create(space=self.space, created_by=self.owner, title="J1 Activity")
        grant_activity_role(
            profile=self.communicator,
            activity=self.activity,
            role_code=SystemRoleCode.ACTIVITY_COMMUNICATION_MANAGER,
            granted_by=self.owner,
            source="j1-test",
        )

    def test_communication_manager_can_manage_conversation_without_activity_manage(self):
        self.assertTrue(can(self.communicator, PermissionCode.ACTIVITY_CONVERSATIONS_MANAGE, activity=self.activity))
        self.assertFalse(can(self.communicator, PermissionCode.ACTIVITY_MANAGE, activity=self.activity))
        conversation = ensure_context_conversation(
            actor=self.communicator,
            kind=ConversationContextKind.ACTIVITY,
            activity=self.activity,
            purpose_key="coordination",
        )
        self.assertEqual(conversation.lifecycle, ConversationLifecycle.OPEN)
        self.assertEqual(conversation.context.activity_id, self.activity.pk)
        self.assertTrue(can_manage_conversation(self.communicator, conversation))
        self.assertFalse(can_manage_conversation(self.outsider, conversation))

    def test_context_conversation_is_idempotent_for_same_context_and_purpose(self):
        first = ensure_context_conversation(actor=self.communicator, kind=ConversationContextKind.ACTIVITY, activity=self.activity, purpose_key="coordination")
        second = ensure_context_conversation(actor=self.communicator, kind=ConversationContextKind.ACTIVITY, activity=self.activity, purpose_key="coordination")
        self.assertEqual(first.pk, second.pk)

    def test_separate_purpose_requires_reason(self):
        with self.assertRaises(ValidationError):
            ensure_context_conversation(actor=self.communicator, kind=ConversationContextKind.ACTIVITY, activity=self.activity, purpose_key="crisis-room")

    def test_outsider_cannot_create_activity_conversation(self):
        with self.assertRaises(PermissionDenied):
            ensure_context_conversation(actor=self.outsider, kind=ConversationContextKind.ACTIVITY, activity=self.activity)

    def test_lifecycle_must_use_service_and_closed_can_reopen(self):
        conversation = ensure_context_conversation(actor=self.communicator, kind=ConversationContextKind.ACTIVITY, activity=self.activity)
        conversation.lifecycle = ConversationLifecycle.CLOSED
        with self.assertRaises(ValidationError):
            conversation.save()
        conversation = transition_conversation(actor=self.communicator, conversation=conversation, lifecycle=ConversationLifecycle.CLOSED)
        self.assertIsNotNone(conversation.closed_at)
        conversation = transition_conversation(actor=self.communicator, conversation=conversation, lifecycle=ConversationLifecycle.OPEN)
        self.assertIsNone(conversation.closed_at)

    def test_policy_preset_changes_capabilities_without_new_authority(self):
        conversation = ensure_context_conversation(actor=self.communicator, kind=ConversationContextKind.ACTIVITY, activity=self.activity)
        policy = set_conversation_policy(actor=self.communicator, conversation=conversation, preset=ConversationModePreset.ANNOUNCEMENTS)
        self.assertFalse(policy.allow_free_exchange)
        self.assertEqual(conversation.pk, policy.conversation_id)
        with self.assertRaises(PermissionDenied):
            set_conversation_policy(actor=self.outsider, conversation=conversation, preset=ConversationModePreset.FREE)
