from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from authorization.constants import PermissionCode
from authorization.services import can
from domain_events.contracts import DomainEventType
from domain_events.services import emit_domain_event

from .models import (
    Form,
    FormAnswer,
    FormQuestion,
    FormRequest,
    FormRequestStatus,
    FormResponse,
    FormResponseStatus,
    FormVersion,
    FormVersionStatus,
    QuestionType,
)


def _require_activity_manage(actor, activity):
    if not getattr(actor, "is_authenticated", False) or not can(actor, PermissionCode.ACTIVITY_MANAGE, activity=activity):
        raise PermissionDenied("La gestion de cette Activity n’est pas autorisée.")


def _require_beneficiary(actor, request):
    if not getattr(actor, "is_authenticated", False) or request.journey.beneficiary_id != actor.pk:
        raise PermissionDenied("Ce formulaire n’appartient pas à votre Journey.")


def _emit(event_type, source_type, source_id, request, suffix, payload):
    activity = request.journey.activity
    return emit_domain_event(
        event_type=event_type,
        source_type=source_type,
        source_id=source_id,
        idempotency_key=f"{source_type}:{source_id}:{suffix}",
        payload=payload,
        space_id=activity.space_id,
        activity_id=activity.pk,
    )


@transaction.atomic
def create_form(*, activity, key, title, description="", actor):
    _require_activity_manage(actor, activity)
    return Form.objects.create(activity=activity, key=key, title=title, description=description, created_by=actor)


@transaction.atomic
def create_form_version(*, form, actor, title=None, description=None):
    _require_activity_manage(actor, form.activity)
    latest = FormVersion.objects.select_for_update().filter(form=form).order_by("-version").first()
    version = 1 if latest is None else latest.version + 1
    return FormVersion.objects.create(
        form=form,
        version=version,
        title=title if title is not None else form.title,
        description=description if description is not None else form.description,
        created_by=actor,
    )


@transaction.atomic
def add_question(*, form_version, actor, key, label, question_type, position, required=False, help_text="", min_length=None, max_length=None, min_value=None, max_value=None, choices=None):
    _require_activity_manage(actor, form_version.form.activity)
    if form_version.status != FormVersionStatus.DRAFT:
        raise ValidationError("Seule une version brouillon peut être modifiée.")
    return FormQuestion.objects.create(
        form_version=form_version,
        key=key,
        label=label,
        help_text=help_text,
        question_type=question_type,
        position=position,
        required=required,
        min_length=min_length,
        max_length=max_length,
        min_value=min_value,
        max_value=max_value,
        choices=choices or [],
    )


@transaction.atomic
def publish_form_version(*, form_version, actor):
    _require_activity_manage(actor, form_version.form.activity)
    form_version = FormVersion.objects.select_for_update().get(pk=form_version.pk)
    if form_version.status != FormVersionStatus.DRAFT:
        raise ValidationError("Cette version n’est plus un brouillon.")
    if not form_version.questions.exists():
        raise ValidationError("Un formulaire publié doit contenir au moins une question.")
    form_version.status = FormVersionStatus.PUBLISHED
    form_version.published_at = timezone.now()
    form_version.save(update_fields=["status", "published_at", "updated_at"])
    return form_version


@transaction.atomic
def request_form(*, form_version, journey, actor, required=True, opens_at=None, due_at=None):
    _require_activity_manage(actor, journey.activity)
    request = FormRequest.objects.create(
        form_version=form_version,
        journey=journey,
        required=required,
        opens_at=opens_at,
        due_at=due_at,
        created_by=actor,
    )
    _emit(
        DomainEventType.FORM_REQUESTED,
        "form_request",
        request.pk,
        request,
        "requested",
        {"form_request_id": str(request.pk), "journey_id": str(journey.pk), "form_version_id": str(form_version.pk)},
    )
    return request


def _validate_answer(question, value):
    if value in (None, "", []):
        if question.required:
            raise ValidationError({question.key: "Ce champ est obligatoire."})
        return None
    if question.question_type in {QuestionType.SHORT_TEXT, QuestionType.LONG_TEXT}:
        if not isinstance(value, str):
            raise ValidationError({question.key: "Une chaîne de caractères est attendue."})
        if question.min_length is not None and len(value) < question.min_length:
            raise ValidationError({question.key: f"Minimum {question.min_length} caractères."})
        if question.max_length is not None and len(value) > question.max_length:
            raise ValidationError({question.key: f"Maximum {question.max_length} caractères."})
        return value
    if question.question_type == QuestionType.BOOLEAN:
        if not isinstance(value, bool):
            raise ValidationError({question.key: "Une valeur booléenne est attendue."})
        return value
    if question.question_type == QuestionType.NUMBER:
        try:
            number = Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError) as exc:
            raise ValidationError({question.key: "Un nombre valide est attendu."}) from exc
        if question.min_value is not None and number < question.min_value:
            raise ValidationError({question.key: f"La valeur minimale est {question.min_value}."})
        if question.max_value is not None and number > question.max_value:
            raise ValidationError({question.key: f"La valeur maximale est {question.max_value}."})
        return str(number)
    if question.question_type == QuestionType.DATE:
        if isinstance(value, date):
            return value.isoformat()
        try:
            return date.fromisoformat(str(value)).isoformat()
        except ValueError as exc:
            raise ValidationError({question.key: "Une date ISO valide est attendue."}) from exc
    if question.question_type == QuestionType.SINGLE_CHOICE:
        if not isinstance(value, str) or value not in question.choices:
            raise ValidationError({question.key: "Le choix fourni n’est pas autorisé."})
        return value
    if question.question_type == QuestionType.MULTIPLE_CHOICE:
        if not isinstance(value, list) or any(item not in question.choices for item in value) or len(set(value)) != len(value):
            raise ValidationError({question.key: "Les choix fournis ne sont pas autorisés."})
        return value
    raise ValidationError({question.key: "Type de question non supporté."})


def _editable(request, now):
    if request.status == FormRequestStatus.CANCELLED:
        return False
    if request.opens_at and now < request.opens_at:
        return False
    response = getattr(request, "response", None)
    if response and response.status == FormResponseStatus.SUBMITTED:
        return False
    if request.due_at and now > request.due_at:
        return False
    return True


@transaction.atomic
def save_response(*, request, actor, answers):
    _require_beneficiary(actor, request)
    now = timezone.now()
    if not _editable(request, now):
        raise ValidationError("Cette réponse n’est pas modifiable actuellement.")
    response, _ = FormResponse.objects.select_for_update().get_or_create(
        request=request,
        defaults={"form_version": request.form_version, "respondent": actor},
    )
    if response.form_version_id != request.form_version_id or response.respondent_id != actor.pk:
        raise ValidationError("La réponse existante ne correspond pas à la demande.")
    questions = {question.key: question for question in request.form_version.questions.all()}
    unknown = set(answers) - set(questions)
    if unknown:
        raise ValidationError({key: "Question inconnue." for key in sorted(unknown)})
    for key, value in answers.items():
        question = questions[key]
        normalized = _validate_answer(question, value)
        FormAnswer.objects.update_or_create(response=response, question=question, defaults={"value": normalized})
    return response


@transaction.atomic
def submit_response(*, request, actor):
    _require_beneficiary(actor, request)
    now = timezone.now()
    if not _editable(request, now):
        raise ValidationError("Cette réponse ne peut pas être soumise actuellement.")
    try:
        response = FormResponse.objects.select_for_update().get(request=request)
    except FormResponse.DoesNotExist as exc:
        raise ValidationError("Enregistrez une réponse avant de la soumettre.") from exc
    existing = {answer.question_id: answer for answer in response.answers.select_related("question")}
    errors = {}
    for question in request.form_version.questions.all():
        answer = existing.get(question.pk)
        try:
            _validate_answer(question, answer.value if answer else None)
        except ValidationError as exc:
            errors[question.key] = exc.messages[0]
    if errors:
        raise ValidationError(errors)
    response.status = FormResponseStatus.SUBMITTED
    response.submitted_at = now
    response.save(update_fields=["status", "submitted_at", "updated_at"])
    request.status = FormRequestStatus.COMPLETED
    request.completed_at = now
    request.save(update_fields=["status", "completed_at", "updated_at"])
    _emit(
        DomainEventType.FORM_SUBMITTED,
        "form_response",
        response.pk,
        request,
        "submitted",
        {"form_response_id": str(response.pk), "form_request_id": str(request.pk), "journey_id": str(request.journey_id)},
    )
    return response


@transaction.atomic
def reopen_response(*, response, actor):
    request = response.request
    _require_activity_manage(actor, request.journey.activity)
    response = FormResponse.objects.select_for_update().get(pk=response.pk)
    if response.status != FormResponseStatus.SUBMITTED:
        raise ValidationError("Seule une réponse soumise peut être réouverte.")
    response.status = FormResponseStatus.REOPENED
    response.reopened_at = timezone.now()
    response.reopened_by = actor
    response.save(update_fields=["status", "reopened_at", "reopened_by", "updated_at"])
    request.status = FormRequestStatus.REQUESTED
    request.completed_at = None
    request.save(update_fields=["status", "completed_at", "updated_at"])
    _emit(
        DomainEventType.FORM_REOPENED,
        "form_response",
        response.pk,
        request,
        f"reopened:{response.reopened_at.isoformat()}",
        {"form_response_id": str(response.pk), "form_request_id": str(request.pk), "journey_id": str(request.journey_id)},
    )
    return response
