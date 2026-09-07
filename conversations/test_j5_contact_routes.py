from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase

from activities.involvement_models import ActivityInvolvement, ActivityInvolvementConfirmationBasis, ActivityInvolvementFunction, ActivityInvolvementFunctionKind
from activities.models import Activity
from authorization.constants import SystemRoleCode
from authorization.services import grant_activity_role
from organizations.models import Organization
from social.models import ActionNetworkBlock

from .audience_models import ConversationAudienceRuleKind, ConversationAudienceRuleOperation
from .audience_services import add_audience_rule, create_audience_set
from .contact_models import CommunicationRouteDestinationKind, CommunicationRouteProvider, ContactIntent
from .contact_services import communication_routes_for, create_communication_route, create_contact_request, ensure_direct_conversation, respond_to_contact_request
from .core_models import ConversationContextKind
from .services import ensure_context_conversation


User = get_user_model()


class ConversationContactTests(TestCase):
    def setUp(self):
        self.a = User.objects.create_user(username="j5-a", email="j5-a@example.test", password="StrongPass2026!")
        self.b = User.objects.create_user(username="j5-b", email="j5-b@example.test", password="StrongPass2026!")

    def test_cold_contact_requires_request_then_converges_to_one_direct_conversation(self):
        request = create_contact_request(actor=self.a, recipient=self.b, intent=ContactIntent.QUESTION, message="Puis-je vous poser une question sur votre activité ?")
        with self.assertRaises(PermissionDenied):
            ensure_direct_conversation(actor=self.a, target=self.b)
        respond_to_contact_request(actor=self.b, contact_request=request, accept=True)
        first = ensure_direct_conversation(actor=self.a, target=self.b)
        second = ensure_direct_conversation(actor=self.b, target=self.a)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(first.context.kind, ConversationContextKind.DIRECT)

    def test_action_network_block_prevents_request_without_disclosing_reason(self):
        ActionNetworkBlock.objects.create(blocker_profile=self.b, blocked_profile=self.a, created_by=self.b)
        with self.assertRaisesMessage(ValidationError, "Cette mise en relation n’est pas disponible."):
            create_contact_request(actor=self.a, recipient=self.b, intent=ContactIntent.QUESTION, message="Question légitime")


class ConversationRouteTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="j5-owner", email="j5-owner@example.test", password="StrongPass2026!")
        self.manager = User.objects.create_user(username="j5-manager", email="j5-manager@example.test", password="StrongPass2026!")
        self.speaker = User.objects.create_user(username="j5-speaker", email="j5-speaker@example.test", password="StrongPass2026!")
        self.outsider = User.objects.create_user(username="j5-outsider", email="j5-outsider@example.test", password="StrongPass2026!")
        self.space = Organization.objects.create(name="J5 Space", created_by=self.owner)
        self.activity = Activity.objects.create(space=self.space, created_by=self.owner, title="J5 Activity")
        grant_activity_role(profile=self.manager, activity=self.activity, role_code=SystemRoleCode.ACTIVITY_COMMUNICATION_MANAGER, granted_by=self.owner, source="j5-test")
        involvement = ActivityInvolvement.objects.create(activity=self.activity, profile=self.speaker, confirmation_basis=ActivityInvolvementConfirmationBasis.PROFILE_CONFIRMED, recorded_by=self.owner, confirmed_by=self.speaker)
        ActivityInvolvementFunction.objects.create(involvement=involvement, kind=ActivityInvolvementFunctionKind.SPEAKER)
        self.conversation = ensure_context_conversation(actor=self.manager, kind=ConversationContextKind.ACTIVITY, activity=self.activity)
        self.speakers = create_audience_set(actor=self.manager, conversation=self.conversation, label="Speakers")
        add_audience_rule(actor=self.manager, audience_set=self.speakers, operation=ConversationAudienceRuleOperation.INCLUDE, kind=ConversationAudienceRuleKind.ACTIVITY_INVOLVEMENT_FUNCTION, activity=self.activity, involvement_function_kind=ActivityInvolvementFunctionKind.SPEAKER)

    def test_external_route_is_visible_only_to_its_audience(self):
        route = create_communication_route(
            actor=self.manager,
            conversation=self.conversation,
            provider=CommunicationRouteProvider.WHATSAPP,
            destination_kind=CommunicationRouteDestinationKind.GROUP_INVITE,
            label="Groupe Speakers",
            destination="test-route-destination",
            audience=self.speakers,
        )
        self.assertIn(route, communication_routes_for(self.speaker, self.conversation))
        self.assertNotIn(route, communication_routes_for(self.outsider, self.conversation))
