from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from activities.models import Activity
from authorization.constants import SystemRoleCode
from authorization.services import grant_activity_role
from domain_events.contracts import DomainEventType
from domain_events.models import DomainEventOutbox
from organizations.models import Organization

from .automation import process_due_conversation_points
from .contact_models import CommunicationRouteDestinationKind, CommunicationRouteProvider, CommunicationRouteStatus
from .contact_services import create_communication_route
from .core_models import ConversationContextKind, ConversationInvitationStatus
from .lifecycle_services import cancel_point, retire_communication_route
from .point_models import ConversationPointKind, ConversationPointLifecycle
from .point_services import create_point
from .services import create_conversation_invitation, ensure_context_conversation


User = get_user_model()


class ConversationLifecycleHardeningTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="j7-life-owner", email="j7-life-owner@example.test", password="StrongPass2026!")
        self.invitee = User.objects.create_user(username="j7-life-invitee", email="j7-life-invitee@example.test", password="StrongPass2026!")
        self.space = Organization.objects.create(name="J7 Lifecycle Space", created_by=self.owner)
        self.activity = Activity.objects.create(space=self.space, created_by=self.owner, title="J7 Lifecycle Activity")
        grant_activity_role(profile=self.owner, activity=self.activity, role_code=SystemRoleCode.ACTIVITY_LOCAL_MANAGER, granted_by=self.owner, source="j7-conversations-lifecycle")
        self.conversation = ensure_context_conversation(actor=self.owner, kind=ConversationContextKind.ACTIVITY, activity=self.activity)

    def test_cancel_point_is_idempotent_and_emits_material_event(self):
        point = create_point(actor=self.owner, conversation=self.conversation, kind=ConversationPointKind.INFORMATION, title="Annulable")
        with self.captureOnCommitCallbacks(execute=True):
            first = cancel_point(actor=self.owner, point=point)
            second = cancel_point(actor=self.owner, point=point)
        self.assertEqual(first.lifecycle, ConversationPointLifecycle.CANCELLED)
        self.assertEqual(second.lifecycle, ConversationPointLifecycle.CANCELLED)
        self.assertEqual(DomainEventOutbox.objects.filter(event_type=DomainEventType.CONVERSATION_POINT_CANCELLED, source_id=str(point.pk)).count(), 1)

    def test_retire_route_is_idempotent_and_emits_event(self):
        with self.captureOnCommitCallbacks(execute=True):
            route = create_communication_route(actor=self.owner, conversation=self.conversation, provider=CommunicationRouteProvider.EMAIL, destination_kind=CommunicationRouteDestinationKind.EMAIL, label="Support", destination="support@example.test")
            first = retire_communication_route(actor=self.owner, route=route)
            second = retire_communication_route(actor=self.owner, route=route)
        self.assertEqual(first.status, CommunicationRouteStatus.RETIRED)
        self.assertEqual(second.status, CommunicationRouteStatus.RETIRED)
        self.assertEqual(DomainEventOutbox.objects.filter(event_type=DomainEventType.CONVERSATION_ROUTE_RETIRED, source_id=str(route.pk)).count(), 1)

    def test_autopilot_expires_pending_invitation(self):
        now = timezone.now()
        invitation = create_conversation_invitation(actor=self.owner, conversation=self.conversation, invitee=self.invitee, expires_at=now - timedelta(minutes=1), client_reference="j7-expiring-invite")
        stats = process_due_conversation_points(now=now)
        invitation.refresh_from_db()
        self.assertEqual(invitation.status, ConversationInvitationStatus.EXPIRED)
        self.assertEqual(stats["invitations_expired"], 1)
        second = process_due_conversation_points(now=now)
        self.assertEqual(second["invitations_expired"], 0)
