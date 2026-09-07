from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from activities.involvement_models import ActivityInvolvement, ActivityInvolvementConfirmationBasis, ActivityInvolvementFunction, ActivityInvolvementFunctionKind
from activities.models import Activity
from authorization.constants import SystemRoleCode
from authorization.services import grant_activity_role
from organizations.models import Organization

from .audience_models import ConversationAudienceRuleKind, ConversationAudienceRuleOperation
from .audience_services import add_audience_rule, create_audience_set
from .core_models import ConversationContextKind
from .point_models import ConversationPointKind, ConversationPointResponseMode
from .point_services import create_point
from .services import ensure_context_conversation


User = get_user_model()


class ConversationExperienceTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="j4-owner", email="j4-owner@example.test", password="StrongPass2026!")
        self.manager = User.objects.create_user(username="j4-manager", email="j4-manager@example.test", password="StrongPass2026!")
        self.member = User.objects.create_user(username="j4-member", email="j4-member@example.test", password="StrongPass2026!")
        self.outsider = User.objects.create_user(username="j4-outsider", email="j4-outsider@example.test", password="StrongPass2026!")
        self.space = Organization.objects.create(name="J4 Space", created_by=self.owner)
        self.activity = Activity.objects.create(space=self.space, created_by=self.owner, title="J4 Activity")
        grant_activity_role(profile=self.manager, activity=self.activity, role_code=SystemRoleCode.ACTIVITY_COMMUNICATION_MANAGER, granted_by=self.owner, source="j4-test")
        involvement = ActivityInvolvement.objects.create(
            activity=self.activity,
            profile=self.member,
            confirmation_basis=ActivityInvolvementConfirmationBasis.PROFILE_CONFIRMED,
            recorded_by=self.owner,
            confirmed_by=self.member,
        )
        ActivityInvolvementFunction.objects.create(involvement=involvement, kind=ActivityInvolvementFunctionKind.SPEAKER)
        self.conversation = ensure_context_conversation(actor=self.manager, kind=ConversationContextKind.ACTIVITY, activity=self.activity)
        self.audience = create_audience_set(actor=self.manager, conversation=self.conversation, label="Intervenants")
        add_audience_rule(actor=self.manager, audience_set=self.audience, operation=ConversationAudienceRuleOperation.INCLUDE, kind=ConversationAudienceRuleKind.ACTIVITY_INVOLVEMENT_FUNCTION, activity=self.activity, involvement_function_kind=ActivityInvolvementFunctionKind.SPEAKER)
        self.point = create_point(
            actor=self.manager,
            conversation=self.conversation,
            kind=ConversationPointKind.QUESTION,
            response_mode=ConversationPointResponseMode.FREE_TEXT,
            title="Votre besoin technique ?",
            visibility_audience=self.audience,
            response_audience=self.audience,
            expected_action_audience=self.audience,
        )

    def test_for_me_lists_attention_not_exchange_volume(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse("conversations:list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "1 pour vous")
        self.assertContains(response, "J4 Activity")

    def test_detail_does_not_leak_to_outsider(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse("conversations:detail", kwargs={"pk": self.conversation.pk}))
        self.assertEqual(response.status_code, 403)

    def test_member_can_respond_from_mature_now_surface(self):
        self.client.force_login(self.member)
        response = self.client.post(
            reverse("conversations:point-respond", kwargs={"point_pk": self.point.pk}),
            {"value": "Un micro casque"},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Tout est en ordre")
        self.assertEqual(self.point.responses.filter(actor=self.member, status="active").count(), 1)
