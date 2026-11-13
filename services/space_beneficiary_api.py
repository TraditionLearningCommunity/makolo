"""Native applicant-Space Service flow (distinct from provider/operator MT4).

The URL selects the represented Space. Every read and command rechecks live
Mandates; there is no implicit actor from the mobile navigation state.
"""
from collections.abc import Mapping

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.api.projections import projection_envelope
from groups.models import ActivityGroupEligibility, ActivityGroupEligibilityStatus
from journeys.models import Journey, JourneyStatus, WorkflowKind
from organizations.models import Organization
from readiness import resolve_journey_readiness

from .api_views import (
    ServiceStartAPIView, _conflict_response, _error_from_owner,
    _public_service_for_viewer,
)
from .forms import ServiceStartForm
from .models import OpportunityPolicy, ServiceIntakeAnswer
from .native_start import (
    ServiceStartIdempotencyConflict, replay_native_start_if_exists,
    start_service_journey_idempotently,
)
from .services import (
    _questions_for_context, answer_intake_question, submit_service_journey,
)
from .space_beneficiary import (
    can_act_for_space, can_act_for_space_service_journey,
    can_read_space_service, can_read_space_service_journey,
)


def _reply(body, *, status=200):
    response = Response(body, status=status)
    response["Cache-Control"] = "private, no-store"
    return response


def _space(request, slug, *, write=False):
    space = Organization.objects.filter(slug=slug).first()
    if space is None or not (
        can_act_for_space(request.user, space) if write
        else can_read_space_service(request.user, space)
    ):
        raise NotFound()
    return space


def _journey(request, slug, journey_id, *, write=False):
    space = _space(request, slug, write=write)
    journey = (
        Journey.objects.select_related(
            "activity", "beneficiary_space", "service_context",
            "service_context__opportunity",
            "service_context__opportunity_revision",
        )
        .filter(pk=journey_id, beneficiary_space=space, workflow=WorkflowKind.SERVICE)
        .first()
    )
    if journey is None or not (
        can_act_for_space_service_journey(request.user, journey) if write
        else can_read_space_service_journey(request.user, journey)
    ):
        raise NotFound()
    return space, journey


def _public_space_service(*, pk, viewer):
    service = _public_service_for_viewer(pk=pk, viewer=viewer)
    # Group eligibility is a Profile-only policy. A Profile's membership
    # cannot silently confer that eligibility upon a represented Space.
    if ActivityGroupEligibility.objects.filter(
        activity_id=service.activity_id,
        status=ActivityGroupEligibilityStatus.APPROVED,
    ).exists():
        raise NotFound()
    return service


class SpaceBeneficiaryServiceStartAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, slug, pk):
        space = _space(request, slug, write=True)
        _public_space_service(pk=pk, viewer=request.user)
        # Same Services owner prevalidation as the existing Profile flow.
        response = ServiceStartAPIView().get(request, pk)
        response.data["beneficiary"] = {
            "kind": "space", "id": str(space.pk),
            "slug": space.slug, "name": space.name,
        }
        response.data["links"]["start"] = reverse(
            "organizations_api:workspace-service-applicant-start",
            kwargs={"slug": space.slug, "pk": pk},
        )
        return response

    def post(self, request, slug, pk):
        space = _space(request, slug, write=True)
        service = _public_space_service(pk=pk, viewer=request.user)
        if not isinstance(request.data, Mapping):
            raise ValidationError({"body": "Un objet JSON est requis."})
        if set(request.data) - {"objective", "opportunity"}:
            raise ValidationError({"body": "Champs non reconnus."})
        key = request.headers.get("Idempotency-Key", "")
        try:
            replay = replay_native_start_if_exists(
                service=service, actor=request.user, operation_key=key,
                objective=request.data.get("objective") or "",
                opportunity_id=request.data.get("opportunity"),
                beneficiary_space=space,
            )
        except ServiceStartIdempotencyConflict:
            return _conflict_response()
        except DjangoValidationError as exc:
            raise _error_from_owner(exc) from exc
        if replay is not None:
            journey, created = replay
        else:
            if (
                service.opportunity_policy == OpportunityPolicy.NONE
                and request.data.get("opportunity")
            ):
                raise ValidationError({
                    "opportunity": "Ce Service n’accepte pas d’opportunité."
                })
            form = ServiceStartForm(data=request.data, service=service)
            if not form.is_valid():
                raise ValidationError(dict(form.errors))
            try:
                journey, created = start_service_journey_idempotently(
                    service=service, actor=request.user, operation_key=key,
                    objective=form.cleaned_data.get("objective") or "",
                    opportunity=form.cleaned_data.get("opportunity"),
                    beneficiary_space=space,
                )
            except ServiceStartIdempotencyConflict:
                return _conflict_response()
            except DjangoValidationError as exc:
                raise _error_from_owner(exc) from exc
            except DjangoPermissionDenied:
                raise NotFound() from None

        return _reply({
            "journey": {
                "kind": "journey", "id": str(journey.pk),
                "workflow": journey.workflow, "status": journey.status,
                "beneficiary": {"kind": "space", "id": str(space.pk)},
            },
            "replayed": not created,
            "space": {"id": str(space.pk), "slug": space.slug},
            "links": {
                "journey": reverse(
                    "organizations_api:workspace-beneficiary-journey",
                    kwargs={"slug": space.slug, "journey_id": journey.pk},
                ),
                "intake": reverse(
                    "organizations_api:workspace-beneficiary-intake",
                    kwargs={"slug": space.slug, "journey_id": journey.pk},
                ),
            },
        }, status=201 if created else 200)


class SpaceBeneficiaryJourneyAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, slug, journey_id):
        space, journey = _journey(request, slug, journey_id)
        from core.api.detail_projections import (
            _journey_step_summaries, _service_request, _service_result,
            _service_requirements, serialize_readiness,
        )
        observed_at = timezone.now()
        readiness = resolve_journey_readiness(journey, viewer=None, observed_at=observed_at)
        write = can_act_for_space_service_journey(request.user, journey)
        context = journey.service_context
        forms = list(journey.form_requests.select_related("form_version").order_by("created_at", "pk"))
        details = {
            "identity": {
                "kind": "journey", "id": str(journey.pk),
                "workflow": journey.workflow,
                "beneficiary": {"kind": "space", "id": str(space.pk)},
            },
            "space": {"id": str(space.pk), "slug": space.slug, "name": space.name},
            "representation": {
                "title": journey.activity.title,
                "summary": journey.activity.short_description or None,
            },
            "state": {"code": journey.status, "label": journey.get_status_display()},
            "readiness": serialize_readiness(readiness),
            "steps": _journey_step_summaries(journey),
            "requirements": _service_requirements(journey),
            "service_request": _service_request(journey),
            "service_result": _service_result(journey),
            "forms": [
                {
                    "id": str(row.pk), "title": row.form_version.title,
                    "status": row.status, "required": row.required,
                    "link": reverse("questionnaire-request-detail", kwargs={"pk": row.pk}),
                }
                for row in forms
            ],
            "capabilities": {
                "view": True,
                "answer_intake": write and journey.status == JourneyStatus.DRAFT,
                "upload_artifact": write,
            },
            "links": {
                "intake": reverse(
                    "organizations_api:workspace-beneficiary-intake",
                    kwargs={"slug": space.slug, "journey_id": journey.pk},
                ),
                "artifacts": reverse(
                    "organizations_api:workspace-beneficiary-artifacts",
                    kwargs={"slug": space.slug, "journey_id": journey.pk},
                ),
            },
        }
        return _reply(projection_envelope(
            projection="space.service.journey.detail",
            data=details,
            generated_at=observed_at,
        ))


class SpaceBeneficiaryIntakeAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @staticmethod
    def _details(journey):
        context = journey.service_context
        questions = list(_questions_for_context(context))
        answers = {
            row.question_id: row.value
            for row in ServiceIntakeAnswer.objects.filter(journey=journey)
        }
        return {
            "journey_id": str(journey.pk),
            "state": journey.status,
            "questions": [
                {
                    "id": str(question.pk), "label": question.prompt,
                    "type": question.question_type, "required": question.is_required,
                    "options": question.options,
                    "value": answers.get(question.pk),
                }
                for question in questions
            ],
            "can_edit": journey.status == JourneyStatus.DRAFT,
        }

    def get(self, request, slug, journey_id):
        _, journey = _journey(request, slug, journey_id, write=True)
        return _reply(self._details(journey))

    def post(self, request, slug, journey_id):
        _, journey = _journey(request, slug, journey_id, write=True)
        if not isinstance(request.data, Mapping):
            raise ValidationError({"body": "Un objet JSON est requis."})
        if set(request.data) - {"answers", "submit"}:
            raise ValidationError({"body": "Champs non reconnus."})
        answers = request.data.get("answers", {})
        if not isinstance(answers, Mapping) or len(answers) > 100:
            raise ValidationError({"answers": "Réponses invalides."})
        if request.data.get("submit", False) not in {True, False}:
            raise ValidationError({"submit": "Booléen requis."})
        questions = {
            str(question.pk): question
            for question in _questions_for_context(journey.service_context)
        }
        if set(answers) - set(questions):
            raise ValidationError({"answers": "Question inconnue."})
        try:
            with transaction.atomic():
                for question_id, value in answers.items():
                    answer_intake_question(
                        journey=journey, question=questions[question_id],
                        value=value, actor=request.user,
                    )
                if request.data.get("submit", False):
                    submit_service_journey(journey=journey, actor=request.user)
        except DjangoValidationError as exc:
            raise _error_from_owner(exc) from exc
        except DjangoPermissionDenied:
            raise NotFound() from None
        journey.refresh_from_db()
        return _reply(self._details(journey))
