from django.conf import settings
from django.core.management import BaseCommand, CommandError

from accounts.models import User
from activities.models import Activity
from journeys.models import Journey
from preparation.models import ResourceKind, ResourceVisibility
from preparation.services import create_resource, publish_resource
from questionnaires.models import Form, FormRequest, QuestionType
from questionnaires.services import (
    add_question,
    create_form,
    create_form_version,
    publish_form_version,
    request_form,
)


class Command(BaseCommand):
    help = "Add deterministic M2 questionnaire/resource browser fixtures after prepare_e2e."

    def handle(self, *args, **options):
        if not getattr(settings, "IS_E2E", False):
            raise CommandError("prepare_m2_e2e est réservé à DJANGO_ENV=e2e.")

        owner = User.objects.get(email="owner@e2e.makolo.test")
        participant = User.objects.get(email="participant@e2e.makolo.test")
        reservation_participant = User.objects.get(email="reservation.participant@e2e.makolo.test")

        registration_activity = Activity.objects.get(title="Inscription communautaire E2E")
        registration_journey = Journey.objects.get(activity=registration_activity, beneficiary=participant)
        registration_form = self._ensure_form(
            actor=owner,
            activity=registration_activity,
            key="m2-preparation",
            title="Informations de préparation E2E",
            question_key="meeting-point",
            question_label="Point de rendez-vous préféré",
            required=True,
        )
        if not FormRequest.objects.filter(journey=registration_journey, form_version=registration_form).exists():
            request_form(form_version=registration_form, journey=registration_journey, actor=owner, required=True)

        if not registration_activity.preparation_resources.filter(key="m2-guide").exists():
            resource = create_resource(
                activity=registration_activity,
                occurrence=registration_journey.occurrence,
                actor=owner,
                key="m2-guide",
                title="Guide de préparation E2E",
                kind=ResourceKind.TEXT,
                text_content="Présentez-vous dix minutes avant le début avec votre confirmation Makolo.",
                visibility=ResourceVisibility.PARTICIPANT,
            )
            publish_resource(resource=resource, actor=owner)

        reservation_activity = Activity.objects.get(title="Réservation sur place E2E")
        reservation_journey = Journey.objects.get(activity=reservation_activity, beneficiary=reservation_participant)
        operator_fixture = self._ensure_form(
            actor=owner,
            activity=reservation_activity,
            key="m2-operator-fixture",
            title="Questionnaire opérateur E2E",
            question_key="notes",
            question_label="Informations utiles",
            required=False,
        )
        if not FormRequest.objects.filter(journey=reservation_journey, form_version=operator_fixture).exists():
            request_form(form_version=operator_fixture, journey=reservation_journey, actor=owner, required=False)

        self.stdout.write(self.style.SUCCESS("Makolo M2 E2E fixtures prepared."))

    def _ensure_form(self, *, actor, activity, key, title, question_key, question_label, required):
        existing = Form.objects.filter(activity=activity, key=key).prefetch_related("versions__questions").first()
        if existing:
            published = existing.versions.filter(status="published").order_by("-version").first()
            if published:
                return published
        form = existing or create_form(activity=activity, key=key, title=title, actor=actor)
        version = create_form_version(form=form, actor=actor)
        add_question(
            form_version=version,
            actor=actor,
            key=question_key,
            label=question_label,
            question_type=QuestionType.SHORT_TEXT,
            position=1,
            required=required,
        )
        return publish_form_version(form_version=version, actor=actor)
