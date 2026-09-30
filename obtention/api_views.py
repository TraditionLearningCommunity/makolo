from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404

from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from activities.models import Occurrence
from journeys.collaboration_services import (
    complete_participant_step,
    complete_step,
    start_participant_step,
    start_step,
)
from journeys.models import JourneyStep
from authorization.constants import PermissionCode
from authorization.services import activity_ids_with_permission, can
from organizations.models import Organization
from readiness import resolve_journey_readiness
from requirements.domain_services import assess_journey_requirement

from .api_serializers import (
    ObtentionConfigurationSerializer,
    ObtentionJourneyCreateSerializer,
    OperatorReceiptSerializer,
    ReceiptSerializer,
    RequirementAssessmentInputSerializer,
)
from .models import (
    ObtentionConfigurationStatus,
    ObtentionDetails,
    ObtentionTarget,
)
from .selectors import (
    fulfillment_for_journey,
    obtention_journey_queryset,
    public_obtentions,
    published_configuration,
)
from .services import (
    activate_obtention_journey,
    create_obtention,
    create_obtention_journey,
    fulfill_obtention_journey,
    record_beneficiary_receipt,
    record_operator_receipt,
    revise_obtention,
)


def _raise_service(exc):
    if isinstance(exc, DjangoPermissionDenied):
        raise PermissionDenied(str(exc)) from exc
    if isinstance(exc, DjangoValidationError):
        if hasattr(exc, "message_dict"):
            raise ValidationError(exc.message_dict) from exc
        raise ValidationError(getattr(exc, "messages", [str(exc)])) from exc
    raise exc


def _plan_steps_payload(configuration):
    template = configuration.journey_plan_template
    if template is None:
        return []
    return [
        {
            "key": step.key,
            "actor_kind": step.actor_kind,
            "kind": step.kind,
            "title": step.title,
            "description": step.description,
            "position": step.position,
            "is_required": step.is_required,
            "relative_due_days": step.relative_due_days,
            "depends_on": [
                dependency.depends_on.key
                for dependency in step.dependencies.all()
            ],
        }
        for step in template.steps.prefetch_related("dependencies__depends_on").all()
    ]


def _requirements_payload(configuration):
    return [
        {
            "key": link.requirement.key,
            "title": link.requirement.title,
            "description": link.requirement.description,
            "mode": link.requirement.mode,
            "is_mandatory": link.requirement.is_mandatory,
            "position": link.position,
            "step_key": link.step_key,
            "evaluator_key": link.requirement.evaluator_key,
            "evaluator_config": link.requirement.evaluator_config,
        }
        for link in configuration.requirement_links.select_related("requirement").all()
    ]


def _configuration_payload(configuration):
    return {
        "version": configuration.version,
        "result_label": configuration.result_label,
        "target_rule": configuration.target_rule,
        "minimum_targets": configuration.minimum_targets,
        "beneficiary_confirmation_required": configuration.beneficiary_confirmation_required,
        "operator_confirmation_required": configuration.operator_confirmation_required,
        "plan_steps": _plan_steps_payload(configuration),
        "requirements": _requirements_payload(configuration),
        "targets": [
            {
                "id": str(target.pk),
                "title": target.title,
                "description": target.description,
                "characteristics": target.characteristics,
                "quantity": str(target.quantity),
                "unit": target.unit,
            }
            for target in configuration.targets.all()
        ],
        "modes": [
            {
                "id": str(mode.pk),
                "code": mode.code,
                "label": mode.label or mode.get_code_display(),
            }
            for mode in configuration.modes.all()
        ],
    }


def _payload(obtention, actor=None):
    configuration = published_configuration(obtention)
    if configuration is None:
        raise NotFound()
    activity = obtention.activity
    manageable = bool(
        actor
        and getattr(actor, "is_authenticated", False)
        and can(actor, PermissionCode.ACTIVITY_MANAGE, activity=activity)
    )
    capabilities = ["view", "start_journey"]
    if manageable:
        capabilities.append("manage")
    return {
        "id": str(obtention.pk),
        "activity": {
            "id": str(activity.pk),
            "title": activity.title,
            "short_description": activity.short_description,
            "description": activity.description,
            "status": activity.status,
            "visibility": activity.visibility,
            "space_id": str(activity.space_id) if activity.space_id else None,
            "owner_profile_id": str(activity.owner_profile_id) if activity.owner_profile_id else None,
        },
        "configuration": _configuration_payload(configuration),
        "capabilities": capabilities,
        "links": {
            "self": f"/api/v1/obtention/{obtention.pk}/",
            "activity": f"/api/v1/activities/{activity.pk}/",
            "start_journey": f"/api/v1/obtention/{obtention.pk}/journeys/",
        },
    }


def _managed_obtention(actor, pk):
    obtention = (
        ObtentionDetails.objects.select_related(
            "activity", "activity__space", "activity__owner_profile"
        )
        .filter(pk=pk)
        .first()
    )
    if obtention is None or not can(
        actor, PermissionCode.ACTIVITY_MANAGE, activity=obtention.activity
    ):
        raise NotFound()
    return obtention


def _journey_for_actor(actor, pk):
    queryset = obtention_journey_queryset()
    allowed = activity_ids_with_permission(actor, PermissionCode.ACTIVITY_MANAGE)
    if allowed is None:
        return get_object_or_404(queryset, pk=pk)
    permission_q = Q(activity_id__in=allowed) if allowed else Q(pk__isnull=True)
    return get_object_or_404(
        queryset.filter(Q(beneficiary=actor) | permission_q).distinct(),
        pk=pk,
    )


def _fulfillment_payload(journey):
    result = fulfillment_for_journey(journey)
    return {
        "result_label": result.configuration.result_label,
        "satisfied_count": result.satisfied_count,
        "required_count": result.required_count,
        "complete": result.complete,
        "targets": [
            {
                "id": str(row.target.pk),
                "title": row.target.title,
                "required_quantity": str(row.target.quantity),
                "received_quantity": str(row.received_quantity),
                "unit": row.target.unit,
                "quantity_satisfied": row.quantity_satisfied,
                "beneficiary_confirmed": row.beneficiary_confirmed,
                "operator_confirmed": row.operator_confirmed,
                "satisfied": row.satisfied,
            }
            for row in result.targets
        ],
    }


def _journey_payload(journey, actor):
    readiness = resolve_journey_readiness(
        journey,
        viewer=actor if journey.beneficiary_id == getattr(actor, "pk", None) else None,
    )
    return {
        "id": str(journey.pk),
        "activity_id": str(journey.activity_id),
        "status": journey.status,
        "workflow": journey.workflow,
        "beneficiary_id": str(journey.beneficiary_id) if journey.beneficiary_id else None,
        "configuration_version": journey.obtention_context.configuration.version,
        "mode": {
            "code": journey.obtention_context.mode.code,
            "label": journey.obtention_context.mode.label
            or journey.obtention_context.mode.get_code_display(),
        },
        "readiness": {
            "status": readiness.status.value,
            "next_action": (
                {
                    "key": readiness.next_action.key,
                    "label": readiness.next_action.label,
                    "url": readiness.next_action.url,
                }
                if readiness.next_action
                else None
            ),
        },
        "fulfillment": _fulfillment_payload(journey),
        "requirements": [
            {
                "id": str(assessment.pk),
                "key": assessment.requirement.key,
                "title": assessment.requirement.title,
                "description": assessment.requirement.description,
                "mode": assessment.requirement.mode,
                "is_mandatory": assessment.requirement.is_mandatory,
                "state": assessment.state,
                "reason_code": assessment.reason_code,
                "note": assessment.note,
                "journey_step_id": str(assessment.journey_step_id) if assessment.journey_step_id else None,
                "assessed_at": assessment.assessed_at,
                "links": {
                    "assess": f"/api/v1/obtention/journeys/{journey.pk}/requirements/{assessment.pk}/assess/",
                },
            }
            for assessment in journey.requirement_assessments.select_related(
                "requirement", "journey_step"
            ).all()
        ],
        "steps": [
            {
                "id": str(step.pk),
                "title": step.title,
                "description": step.description,
                "kind": step.kind,
                "status": step.status,
                "is_required": step.is_required,
                "due_at": step.due_at,
                "links": {
                    "start": f"/api/v1/obtention/journeys/{journey.pk}/steps/{step.pk}/start/",
                    "complete": f"/api/v1/obtention/journeys/{journey.pk}/steps/{step.pk}/complete/",
                },
            }
            for step in journey.steps.all()
        ],
        "links": {
            "self": f"/api/v1/obtention/journeys/{journey.pk}/",
            "fulfill": f"/api/v1/obtention/journeys/{journey.pk}/fulfill/",
        },
    }


class ObtentionListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        allowed = activity_ids_with_permission(
            request.user, PermissionCode.ACTIVITY_MANAGE
        )
        queryset = ObtentionDetails.objects.select_related(
            "activity", "activity__space", "activity__owner_profile"
        )
        if allowed is not None:
            permission_q = Q(activity_id__in=allowed) if allowed else Q(pk__isnull=True)
            queryset = queryset.filter(
                Q(activity__owner_profile=request.user) | permission_q
            )
        rows = [_payload(row, request.user) for row in queryset.order_by("activity__title")[:100]]
        response = Response(rows)
        response["Cache-Control"] = "private, no-store"
        return response

    def post(self, request):
        serializer = ObtentionConfigurationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        space_id = data.pop("space_id", None)
        space = get_object_or_404(Organization, pk=space_id) if space_id else None
        try:
            obtention = create_obtention(
                actor=request.user,
                space=space,
                **data,
            )
        except (DjangoPermissionDenied, DjangoValidationError) as exc:
            _raise_service(exc)
        response = Response(_payload(obtention, request.user), status=201)
        response["Cache-Control"] = "private, no-store"
        return response


class ObtentionDetailAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, pk):
        obtention = public_obtentions().filter(pk=pk).first()
        if obtention is None and getattr(request.user, "is_authenticated", False):
            try:
                obtention = _managed_obtention(request.user, pk)
            except NotFound:
                obtention = None
        if obtention is None:
            raise NotFound()
        response = Response(_payload(obtention, request.user))
        if "manage" in response.data["capabilities"]:
            response["Cache-Control"] = "private, no-store"
        return response

    def patch(self, request, pk):
        if not getattr(request.user, "is_authenticated", False):
            raise NotFound()
        obtention = _managed_obtention(request.user, pk)
        configuration = published_configuration(obtention)
        if configuration is None:
            raise NotFound()
        current = {
            "title": obtention.activity.title,
            "short_description": obtention.activity.short_description,
            "description": obtention.activity.description,
            "targets": [
                {
                    "title": target.title,
                    "description": target.description,
                    "characteristics": target.characteristics,
                    "quantity": str(target.quantity),
                    "unit": target.unit,
                }
                for target in configuration.targets.all()
            ],
            "modes": list(configuration.modes.values_list("code", flat=True)),
            "result_label": configuration.result_label,
            "target_rule": configuration.target_rule,
            "minimum_targets": configuration.minimum_targets,
            "beneficiary_confirmation_required": configuration.beneficiary_confirmation_required,
            "operator_confirmation_required": configuration.operator_confirmation_required,
            "plan_steps": _plan_steps_payload(configuration),
            "requirements": _requirements_payload(configuration),
            "status": obtention.activity.status,
            "visibility": obtention.activity.visibility,
        }
        current.update(request.data)
        serializer = ObtentionConfigurationSerializer(data=current)
        serializer.is_valid(raise_exception=True)
        try:
            obtention = revise_obtention(
                obtention=obtention,
                actor=request.user,
                **serializer.validated_data,
            )
        except (DjangoPermissionDenied, DjangoValidationError) as exc:
            _raise_service(exc)
        response = Response(_payload(obtention, request.user))
        response["Cache-Control"] = "private, no-store"
        return response


class ObtentionJourneyCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        obtention = get_object_or_404(public_obtentions(), pk=pk)
        serializer = ObtentionJourneyCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        occurrence_id = data.pop("occurrence_id", None)
        occurrence = None
        if occurrence_id:
            occurrence = get_object_or_404(
                Occurrence,
                pk=occurrence_id,
                activity=obtention.activity,
            )
        try:
            journey = create_obtention_journey(
                obtention=obtention,
                actor=request.user,
                occurrence=occurrence,
                **data,
            )
            journey = activate_obtention_journey(
                journey=journey,
                actor=request.user,
            )
        except (DjangoPermissionDenied, DjangoValidationError) as exc:
            _raise_service(exc)
        journey = _journey_for_actor(request.user, journey.pk)
        response = Response(_journey_payload(journey, request.user), status=201)
        response["Cache-Control"] = "private, no-store"
        return response


class ObtentionJourneyAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        response = Response(
            _journey_payload(_journey_for_actor(request.user, pk), request.user)
        )
        response["Cache-Control"] = "private, no-store"
        return response


class ObtentionReceiptAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk, target_id):
        journey = _journey_for_actor(request.user, pk)
        target = get_object_or_404(
            ObtentionTarget,
            pk=target_id,
            configuration=journey.obtention_context.configuration,
        )
        serializer = ReceiptSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            record_beneficiary_receipt(
                journey=journey,
                target=target,
                actor=request.user,
                **serializer.validated_data,
            )
        except (DjangoPermissionDenied, DjangoValidationError) as exc:
            _raise_service(exc)
        journey = _journey_for_actor(request.user, pk)
        response = Response(_journey_payload(journey, request.user))
        response["Cache-Control"] = "private, no-store"
        return response


class ObtentionOperatorReceiptAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk, target_id):
        journey = _journey_for_actor(request.user, pk)
        if not can(
            request.user,
            PermissionCode.ACTIVITY_MANAGE,
            activity=journey.activity,
        ):
            raise NotFound()
        target = get_object_or_404(
            ObtentionTarget,
            pk=target_id,
            configuration=journey.obtention_context.configuration,
        )
        serializer = OperatorReceiptSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            record_operator_receipt(
                journey=journey,
                target=target,
                actor=request.user,
                **serializer.validated_data,
            )
        except (DjangoPermissionDenied, DjangoValidationError) as exc:
            _raise_service(exc)
        journey = _journey_for_actor(request.user, pk)
        response = Response(_journey_payload(journey, request.user))
        response["Cache-Control"] = "private, no-store"
        return response


class ObtentionFulfillAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        journey = _journey_for_actor(request.user, pk)
        try:
            fulfill_obtention_journey(journey=journey, actor=request.user)
        except (DjangoPermissionDenied, DjangoValidationError) as exc:
            _raise_service(exc)
        journey = _journey_for_actor(request.user, pk)
        response = Response(_journey_payload(journey, request.user))
        response["Cache-Control"] = "private, no-store"
        return response


class ObtentionStepStartAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk, step_id):
        journey = _journey_for_actor(request.user, pk)
        step = get_object_or_404(JourneyStep, pk=step_id, journey=journey)
        try:
            if journey.beneficiary_id == request.user.pk:
                start_participant_step(step=step, actor=request.user)
            else:
                start_step(step=step, actor=request.user)
        except (DjangoPermissionDenied, DjangoValidationError) as exc:
            _raise_service(exc)
        journey = _journey_for_actor(request.user, pk)
        response = Response(_journey_payload(journey, request.user))
        response["Cache-Control"] = "private, no-store"
        return response


class ObtentionStepCompleteAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk, step_id):
        journey = _journey_for_actor(request.user, pk)
        step = get_object_or_404(JourneyStep, pk=step_id, journey=journey)
        try:
            if journey.beneficiary_id == request.user.pk:
                complete_participant_step(step=step, actor=request.user)
            else:
                complete_step(step=step, actor=request.user)
        except (DjangoPermissionDenied, DjangoValidationError) as exc:
            _raise_service(exc)
        journey = _journey_for_actor(request.user, pk)
        response = Response(_journey_payload(journey, request.user))
        response["Cache-Control"] = "private, no-store"
        return response


class ObtentionRequirementAssessmentAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk, assessment_id):
        journey = _journey_for_actor(request.user, pk)
        if not can(
            request.user,
            PermissionCode.ACTIVITY_MANAGE,
            activity=journey.activity,
        ):
            raise NotFound()
        assessment = get_object_or_404(
            journey.requirement_assessments.select_related(
                "journey__activity",
                "requirement",
            ),
            pk=assessment_id,
        )
        serializer = RequirementAssessmentInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            assess_journey_requirement(
                assessment=assessment,
                actor=request.user,
                reason_code="obtention_operator_assessment",
                **serializer.validated_data,
            )
        except (DjangoPermissionDenied, DjangoValidationError) as exc:
            _raise_service(exc)
        journey = _journey_for_actor(request.user, pk)
        response = Response(_journey_payload(journey, request.user))
        response["Cache-Control"] = "private, no-store"
        return response
