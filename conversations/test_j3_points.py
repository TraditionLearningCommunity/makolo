from django.contrib.auth import get_user_model
from django.test import TestCase

from activities.involvement_models import ActivityInvolvement, ActivityInvolvementConfirmationBasis, ActivityInvolvementFunction, ActivityInvolvementFunctionKind
from activities.models import Activity
from authorization.constants import SystemRoleCode
from authorization.services import grant_activity_role
from organizations.models import Organization

from .attention import attention_points_for_profile
from .audience_models import ConversationAudienceRuleKind, ConversationAudienceRuleOperation
from .audience_services import add_audience_rule, create_audience_set
from .core_models import ConversationContextKind
from .point_models import ConversationPointKind, ConversationPointLifecycle, ConversationPointResolutionPolicy, ConversationPointResponseMode
from .point_services import acknowledge_point, close_point_responses, create_exchange_entry, create_point, submit_point_response, supersede_point
from .services import ensure_context_conversation


User = get_user_model()


class ConversationPointTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="j3-owner", email="j3-owner@example.test", password="StrongPass2026!")
        self.manager = User.objects.create_user(username="j3-manager", email="j3-manager@example.test", password="StrongPass2026!")
        self.a = User.objects.create_user(username="j3-a", email="j3-a@example.test", password="StrongPass2026!")
        self.b = User.objects.create_user(username="j3-b", email="j3-b@example.test", password="StrongPass2026!")
        self.c = User.objects.create_user(username="j3-c", email="j3-c@example.test", password="StrongPass2026!")
        self.space = Organization.objects.create(name="J3 Space", created_by=self.owner)
        self.activity = Activity.objects.create(space=self.space, created_by=self.owner, title="J3 Activity")
        grant_activity_role(profile=self.manager, activity=self.activity, role_code=SystemRoleCode.ACTIVITY_COMMUNICATION_MANAGER, granted_by=self.owner, source="j3-test")
        self.conversation = ensure_context_conversation(actor=self.manager, kind=ConversationContextKind.ACTIVITY, activity=self.activity)
        for profile in (self.a, self.b, self.c):
            involvement = ActivityInvolvement.objects.create(
                activity=self.activity,
                profile=profile,
                confirmation_basis=ActivityInvolvementConfirmationBasis.PROFILE_CONFIRMED,
                recorded_by=self.owner,
                confirmed_by=profile,
            )
            ActivityInvolvementFunction.objects.create(involvement=involvement, kind=ActivityInvolvementFunctionKind.SPEAKER)
        self.speakers = create_audience_set(actor=self.manager, conversation=self.conversation, label="Speakers")
        add_audience_rule(
            actor=self.manager,
            audience_set=self.speakers,
            operation=ConversationAudienceRuleOperation.INCLUDE,
            kind=ConversationAudienceRuleKind.ACTIVITY_INVOLVEMENT_FUNCTION,
            activity=self.activity,
            involvement_function_kind=ActivityInvolvementFunctionKind.SPEAKER,
        )

    def test_plurality_resolves_at_response_close_not_after_first_vote(self):
        point = create_point(
            actor=self.manager,
            conversation=self.conversation,
            kind=ConversationPointKind.POLL,
            response_mode=ConversationPointResponseMode.SINGLE_CHOICE,
            resolution_policy=ConversationPointResolutionPolicy.PLURALITY,
            title="Heure de répétition",
            visibility_audience=self.speakers,
            response_audience=self.speakers,
            expected_action_audience=self.speakers,
            options=("15h40", "16h30", "20h00"),
        )
        options = list(point.options.order_by("position"))
        submit_point_response(actor=self.a, point=point, value=str(options[1].pk))
        point.refresh_from_db()
        self.assertEqual(point.lifecycle, ConversationPointLifecycle.OPEN)
        submit_point_response(actor=self.b, point=point, value=str(options[1].pk))
        submit_point_response(actor=self.c, point=point, value=str(options[0].pk))
        point = close_point_responses(actor=self.manager, point=point)
        self.assertEqual(point.lifecycle, ConversationPointLifecycle.RESOLVED)
        selected = point.resolution.selected_option_links.get().option
        self.assertEqual(selected.label, "16h30")

    def test_expected_question_is_attention_until_response(self):
        point = create_point(
            actor=self.manager,
            conversation=self.conversation,
            kind=ConversationPointKind.QUESTION,
            response_mode=ConversationPointResponseMode.FREE_TEXT,
            title="Votre besoin technique ?",
            visibility_audience=self.speakers,
            response_audience=self.speakers,
            expected_action_audience=self.speakers,
        )
        before = {item.point_id for item in attention_points_for_profile(self.a)}
        self.assertIn(point.pk, before)
        submit_point_response(actor=self.a, point=point, value="Un micro casque")
        after = {item.point_id for item in attention_points_for_profile(self.a)}
        self.assertNotIn(point.pk, after)

    def test_acknowledgement_is_distinct_from_seen_and_clears_attention(self):
        point = create_point(
            actor=self.manager,
            conversation=self.conversation,
            kind=ConversationPointKind.INFORMATION,
            title="Entrée par la porte B",
            visibility_audience=self.speakers,
            expected_action_audience=self.speakers,
            requires_acknowledgement=True,
        )
        self.assertIn(point.pk, {item.point_id for item in attention_points_for_profile(self.a)})
        state = acknowledge_point(actor=self.a, point=point)
        self.assertIsNotNone(state.acknowledged_at)
        self.assertNotIn(point.pk, {item.point_id for item in attention_points_for_profile(self.a)})

    def test_supersession_keeps_history_but_replaces_operational_point(self):
        old = create_point(actor=self.manager, conversation=self.conversation, kind=ConversationPointKind.INFORMATION, title="Entrée porte C")
        new = create_point(actor=self.manager, conversation=self.conversation, kind=ConversationPointKind.INFORMATION, title="Entrée porte B", publish=False)
        supersede_point(actor=self.manager, old_point=old, new_point=new)
        old.refresh_from_db(); new.refresh_from_db()
        self.assertEqual(old.lifecycle, ConversationPointLifecycle.SUPERSEDED)
        self.assertEqual(new.lifecycle, ConversationPointLifecycle.OPEN)
        self.assertEqual(new.supersedes_id, old.pk)

    def test_free_exchange_does_not_create_attention_by_itself(self):
        point = create_point(
            actor=self.manager,
            conversation=self.conversation,
            kind=ConversationPointKind.EXCHANGE,
            response_mode=ConversationPointResponseMode.FREE_TEXT,
            visibility_audience=self.speakers,
            response_audience=self.speakers,
            title="Questions libres",
        )
        create_exchange_entry(actor=self.a, point=point, body="Je serai sur place à 15h.")
        self.assertNotIn(point.pk, {item.point_id for item in attention_points_for_profile(self.b)})
