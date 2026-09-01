from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.urls import reverse

from activities.services import create_activity
from journeys.models import Journey, JourneyStatus, WorkflowKind
from readiness import resolve_journey_readiness

from .models import FormVersionStatus, QuestionType
from .services import (
    add_question,
    create_form,
    create_form_version,
    publish_form_version,
    request_form,
    save_response,
    submit_response,
)


User = get_user_model()


class QuestionnaireM2Tests(TestCase):
    def setUp(self):
        self.operator = User.objects.create_user(username="m2-operator", email="m2-operator@example.test", password="StrongPass2026!")
        self.participant = User.objects.create_user(username="m2-participant", email="m2-participant@example.test", password="StrongPass2026!")
        self.other = User.objects.create_user(username="m2-other", email="m2-other@example.test", password="StrongPass2026!")
        self.activity = create_activity(owner_profile=self.operator, created_by=self.operator, title="Atelier préparation")
        self.journey = Journey.objects.create(
            initiated_by=self.participant,
            beneficiary=self.participant,
            activity=self.activity,
            workflow=WorkflowKind.REGISTRATION,
            status=JourneyStatus.CONFIRMED,
        )
        self.form = create_form(activity=self.activity, key="participant-info", title="Informations du participant", actor=self.operator)
        self.v1 = create_form_version(form=self.form, actor=self.operator)
        self.name_q = add_question(
            form_version=self.v1,
            actor=self.operator,
            key="display-name",
            label="Nom affiché",
            question_type=QuestionType.SHORT_TEXT,
            position=1,
            required=True,
            min_length=2,
            max_length=80,
        )
        self.choice_q = add_question(
            form_version=self.v1,
            actor=self.operator,
            key="needs",
            label="Besoins",
            question_type=QuestionType.MULTIPLE_CHOICE,
            position=2,
            choices=["Accueil", "Accessibilité"],
        )
        publish_form_version(form_version=self.v1, actor=self.operator)

    def test_published_version_is_stable_and_new_version_is_distinct(self):
        self.assertEqual(self.v1.status, FormVersionStatus.PUBLISHED)
        self.v1.title = "Mutation interdite"
        with self.assertRaises(ValidationError):
            self.v1.save()
        v2 = create_form_version(form=self.form, actor=self.operator)
        self.assertEqual(v2.version, 2)
        self.assertEqual(v2.status, FormVersionStatus.DRAFT)

    def test_request_response_submission_is_version_pinned_and_server_validated(self):
        form_request = request_form(form_version=self.v1, journey=self.journey, actor=self.operator, required=True)
        with self.assertRaises(ValidationError):
            save_response(request=form_request, actor=self.participant, answers={"display-name": "x"})
        response = save_response(
            request=form_request,
            actor=self.participant,
            answers={"display-name": "Gil", "needs": ["Accueil"]},
        )
        self.assertEqual(response.form_version_id, self.v1.pk)
        submitted = submit_response(request=form_request, actor=self.participant)
        self.assertEqual(submitted.status, "submitted")
        form_request.refresh_from_db()
        self.assertEqual(form_request.status, "completed")
        with self.assertRaises(ValidationError):
            save_response(request=form_request, actor=self.participant, answers={"display-name": "Autre"})

    def test_required_form_contributes_to_readiness_then_is_satisfied(self):
        form_request = request_form(form_version=self.v1, journey=self.journey, actor=self.operator, required=True)
        result = resolve_journey_readiness(self.journey, viewer=self.participant)
        check = next(item for item in result.checks if item.key == f"form_request.{form_request.pk}")
        self.assertEqual(check.reason_code, "form_response_required")
        self.assertEqual(check.state, "action_required")
        self.assertIn(str(form_request.pk), check.next_action.url)
        save_response(request=form_request, actor=self.participant, answers={"display-name": "Gil"})
        submit_response(request=form_request, actor=self.participant)
        self.journey = Journey.objects.get(pk=self.journey.pk)
        result = resolve_journey_readiness(self.journey, viewer=self.participant)
        check = next(item for item in result.checks if item.key == f"form_request.{form_request.pk}")
        self.assertEqual(check.reason_code, "form_response_submitted")
        self.assertEqual(check.state, "satisfied")

    def test_optional_form_does_not_block_readiness(self):
        form_request = request_form(form_version=self.v1, journey=self.journey, actor=self.operator, required=False)
        result = resolve_journey_readiness(self.journey, viewer=self.participant)
        self.assertFalse(any(item.key == f"form_request.{form_request.pk}" for item in result.checks))

    def test_other_participant_cannot_read_or_write_request(self):
        form_request = request_form(form_version=self.v1, journey=self.journey, actor=self.operator)
        with self.assertRaises(PermissionDenied):
            save_response(request=form_request, actor=self.other, answers={"display-name": "Intrus"})
        self.client.force_login(self.other)
        response = self.client.get(reverse("questionnaires:request-detail", kwargs={"pk": form_request.pk}))
        self.assertEqual(response.status_code, 404)

    def test_operator_authority_does_not_come_from_being_arbitrary_user(self):
        with self.assertRaises(PermissionDenied):
            create_form(activity=self.activity, key="forbidden", title="Interdit", actor=self.other)

    def test_api_rejects_idor_and_accepts_own_draft(self):
        form_request = request_form(form_version=self.v1, journey=self.journey, actor=self.operator)
        self.client.force_login(self.other)
        url = reverse("questionnaire-request-detail", kwargs={"pk": form_request.pk})
        self.assertEqual(self.client.get(url).status_code, 404)
        self.client.force_login(self.participant)
        save_url = reverse("questionnaire-response-save", kwargs={"pk": form_request.pk})
        response = self.client.post(save_url, data={"answers": {"display-name": "Gil"}}, content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["response"]["status"], "draft")
