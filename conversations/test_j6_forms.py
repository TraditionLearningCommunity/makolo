from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from activities.models import Activity
from authorization.constants import SystemRoleCode
from authorization.services import grant_activity_role
from organizations.models import Organization
from questionnaires.models import FormRequestStatus, QuestionType
from questionnaires.services import (
    add_question,
    create_form,
    create_form_version,
    publish_form_version,
    request_form_for_profile,
    save_response,
    submit_response,
)

from .attention import point_attention_reason
from .audience_models import ConversationAudienceRuleKind, ConversationAudienceRuleOperation
from .audience_services import add_audience_rule, create_audience_set
from .core_models import ConversationContextKind
from .form_services import ensure_form_requests_for_point, form_request_for_profile
from .point_models import ConversationPointKind, ConversationPointResponseMode
from .point_services import create_point
from .services import activate_participation, ensure_context_conversation


User = get_user_model()


class ConversationFormsTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="j6-owner", email="j6-owner@example.test", password="StrongPass2026!")
        self.member = User.objects.create_user(username="j6-member", email="j6-member@example.test", password="StrongPass2026!")
        self.outsider = User.objects.create_user(username="j6-outsider", email="j6-outsider@example.test", password="StrongPass2026!")
        self.space = Organization.objects.create(name="J6 Space", created_by=self.owner)
        self.activity = Activity.objects.create(space=self.space, created_by=self.owner, title="J6 Activity")
        grant_activity_role(
            profile=self.owner,
            activity=self.activity,
            role_code=SystemRoleCode.ACTIVITY_LOCAL_MANAGER,
            granted_by=self.owner,
            source="j6-conversations-forms",
        )
        self.form = create_form(activity=self.activity, key="coordination", title="Préparation collective", actor=self.owner)
        self.version = create_form_version(form=self.form, actor=self.owner)
        add_question(
            form_version=self.version,
            actor=self.owner,
            key="need",
            label="De quoi avez-vous besoin ?",
            question_type=QuestionType.SHORT_TEXT,
            position=0,
            required=True,
        )
        publish_form_version(form_version=self.version, actor=self.owner)

    def _form_point(self):
        conversation = ensure_context_conversation(
            actor=self.owner,
            kind=ConversationContextKind.ACTIVITY,
            activity=self.activity,
        )
        # Explicit Point audiences narrow an existing live boundary; they do not
        # create Conversation access by themselves.
        activate_participation(actor=self.owner, conversation=conversation, profile=self.member)
        audience = create_audience_set(actor=self.owner, conversation=conversation, label="Cible")
        add_audience_rule(
            actor=self.owner,
            audience_set=audience,
            operation=ConversationAudienceRuleOperation.INCLUDE,
            kind=ConversationAudienceRuleKind.EXPLICIT_PROFILE,
            profile=self.member,
        )
        point = create_point(
            actor=self.owner,
            conversation=conversation,
            kind=ConversationPointKind.FORM_REQUEST,
            response_mode=ConversationPointResponseMode.NONE,
            title="Préparer votre intervention",
            visibility_audience=audience,
            expected_action_audience=audience,
        )
        return conversation, point

    def test_profile_targeted_form_request_is_not_a_journey_request(self):
        form_request = request_form_for_profile(
            form_version=self.version,
            profile=self.member,
            actor=self.owner,
        )
        self.assertIsNone(form_request.journey_id)
        self.assertEqual(form_request.target_profile_id, self.member.pk)
        self.assertEqual(form_request.recipient, self.member)
        self.assertEqual(form_request.activity, self.activity)

    def test_profile_target_can_save_and_submit_existing_form_engine(self):
        form_request = request_form_for_profile(
            form_version=self.version,
            profile=self.member,
            actor=self.owner,
        )
        response = save_response(request=form_request, actor=self.member, answers={"need": "Un micro"})
        self.assertEqual(response.respondent_id, self.member.pk)
        submit_response(request=form_request, actor=self.member)
        form_request.refresh_from_db()
        self.assertEqual(form_request.status, FormRequestStatus.COMPLETED)

    def test_wrong_profile_cannot_open_targeted_request(self):
        form_request = request_form_for_profile(
            form_version=self.version,
            profile=self.member,
            actor=self.owner,
        )
        self.client.force_login(self.outsider)
        response = self.client.get(reverse("questionnaires:request-detail", kwargs={"pk": form_request.pk}))
        self.assertEqual(response.status_code, 404)

    def test_conversation_form_bridge_clears_attention_only_after_submission(self):
        conversation, point = self._form_point()
        links = ensure_form_requests_for_point(actor=self.owner, point=point, form_version=self.version)
        self.assertEqual(len(links), 1)
        form_request = form_request_for_profile(point, self.member)
        self.assertIsNotNone(form_request)
        self.assertEqual(point_attention_reason(self.member, point), "form")

        self.client.force_login(self.member)
        detail = self.client.get(reverse("conversations:detail", kwargs={"pk": conversation.pk}))
        self.assertContains(detail, "Compléter le formulaire")

        save_response(request=form_request, actor=self.member, answers={"need": "Un micro"})
        self.assertEqual(point_attention_reason(self.member, point), "form")
        submit_response(request=form_request, actor=self.member)
        self.assertIsNone(point_attention_reason(self.member, point))

    def test_form_bridge_is_idempotent_for_same_point_and_profile(self):
        _, point = self._form_point()
        first = ensure_form_requests_for_point(actor=self.owner, point=point, form_version=self.version)
        second = ensure_form_requests_for_point(actor=self.owner, point=point, form_version=self.version)
        self.assertEqual(first[0].pk, second[0].pk)
        self.assertEqual(point.form_request_links.count(), 1)
