"""Lot 7: Questionnaire media stay with the canonical FormVersion owner."""
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase

from activities.models import Activity
from authorization.constants import SystemRoleCode
from authorization.services import grant_activity_role
from organizations.models import Organization

from .media_services import ensure_media_access, media_sections
from .models import QuestionnaireMedia, QuestionType
from .services import (
    add_question, create_form, create_form_version, publish_form_version,
    request_form_for_profile,
)

User = get_user_model()


class Lot7QuestionnaireMediaContracts(TestCase):
    def setUp(self):
        self.manager = User.objects.create_user(
            username="lot7-form-manager", password="StrongPass2026!",
        )
        self.target = User.objects.create_user(
            username="lot7-form-target", password="StrongPass2026!",
        )
        self.outsider = User.objects.create_user(
            username="lot7-form-outsider", password="StrongPass2026!",
        )
        self.space = Organization.objects.create(
            name="Lot7 Media Form", created_by=self.manager,
        )
        self.activity = Activity.objects.create(
            space=self.space, created_by=self.manager,
            title="Lot7 Media Activity",
        )
        grant_activity_role(
            profile=self.manager, activity=self.activity,
            role_code=SystemRoleCode.ACTIVITY_LOCAL_MANAGER,
            granted_by=self.manager, source="lot7-questionnaire-media",
        )
        form = create_form(
            activity=self.activity, key="lot7-media",
            title="Questionnaire enrichi", actor=self.manager,
        )
        self.version = create_form_version(form=form, actor=self.manager)
        self.question = add_question(
            actor=self.manager, form_version=self.version,
            key="choice", label="Choisissez", question_type=QuestionType.SINGLE_CHOICE,
            position=0, choices=["Oui", "Non"], required=True,
        )

    def _media(self, *, question=None, choice_index=None, position=0):
        return QuestionnaireMedia.objects.create(
            form_version=self.version,
            question=question,
            choice_index=choice_index,
            position=position,
            uploaded_by=self.manager,
            kind="image",
            file="questionnaires/tests/media-immutable.bin",
            original_name="explication.png",
            mime_type="image/png",
            size=50,
            content_hash="a" * 64,
        )

    def test_media_relations_preserve_root_question_and_choice_hierarchy(self):
        root = self._media(position=0)
        question = self._media(question=self.question, position=1)
        choice = self._media(question=self.question, choice_index=1, position=2)
        overall, by_question, by_choice = media_sections(self.version)
        self.assertEqual([item.pk for item in overall], [root.pk])
        self.assertEqual(
            [item.pk for item in by_question[self.question.pk]], [question.pk],
        )
        self.assertEqual(
            [item.pk for item in by_choice[(self.question.pk, 1)]], [choice.pk],
        )
        self.assertFalse(
            QuestionnaireMedia.objects.filter(
                form_version=self.version, question__isnull=False,
                choice_index__isnull=True, pk=choice.pk,
            ).exists(),
        )
        self.assertEqual(self.version.media.count(), 3)

    def test_choice_media_prevents_silent_reassignment_of_published_meaning(self):
        media = self._media(question=self.question, choice_index=0)
        self.question.choices = ["Autre", "Non"]
        with self.assertRaises(ValidationError):
            self.question.save()
        self.question.refresh_from_db()
        self.assertEqual(self.question.choices, ["Oui", "Non"])
        self.assertEqual(media.choice_index, 0)

    def test_media_access_respects_form_target_and_published_version_immutability(self):
        media = self._media(question=self.question)
        publish_form_version(form_version=self.version, actor=self.manager)
        with self.assertRaises(PermissionDenied):
            ensure_media_access(self.target, media)
        with self.assertRaises(PermissionDenied):
            ensure_media_access(self.outsider, media)

        request_form_for_profile(
            form_version=self.version, profile=self.target, actor=self.manager,
        )
        ensure_media_access(self.target, media)
        ensure_media_access(self.manager, media)
        with self.assertRaises(PermissionDenied):
            ensure_media_access(self.outsider, media)

        media.caption = "Modification tardive"
        with self.assertRaises(ValidationError):
            media.save()
