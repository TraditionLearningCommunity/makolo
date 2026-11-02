"""MT4 — Native operator dossier reading and owner action handoff.

Services retains JourneySteps, Blockers, Requirements, evidence and outcomes.
This endpoint only projects bounded, authorized facts and delegates transitions
to the existing collaboration services under the Services permission policy.
"""
from uuid import UUID

from django.core.exceptions import (
    PermissionDenied as DjangoPermissionDenied,
    ValidationError as DjangoValidationError,
)
from django.db.models import Count, Q
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from authorization.constants import PermissionCode
from authorization.services import can
from journeys.collaboration_models import (
    JourneyBlocker, JourneyBlockerStatus, JourneyStep, JourneyStepStatus,
)
from journeys.collaboration_services import (
    complete_step, resolve_blocker, start_step,
)
from journeys.service_authorization import (
    CASE_SCOPE_VIEW_ALL, CASE_SCOPE_VIEW_ASSIGNED, service_case_scope,
)
from organizations.models import SpaceArchetype
from requirements.contracts import RequirementAssessmentState
from services.models import ServiceRequirementAssessment
from services.selectors import service_journeys_visible_to

from .space_work_projection import (
    _activity_scope_from_responsibility, _visible_activity_ids,
)
from .workspace_projection import workspace_spaces


class SpaceG2ServiceCaseAPIView(APIView):
    permission_classes = [IsAuthenticated]
    _scopes = {CASE_SCOPE_VIEW_ALL, CASE_SCOPE_VIEW_ASSIGNED}

    @staticmethod
    def _reply(data, status=200):
        response = Response(data, status=status)
        response["Cache-Control"] = "private, no-store"
        return response

    def _owner(self, request, slug, journey_id):
        space = workspace_spaces(request.user).filter(slug=slug).first()
        if space is None or space.archetype != SpaceArchetype.SERVICE_PROVIDER:
            raise NotFound()
        responsibility = (
            request.query_params.get("responsibility") or "all"
        ).strip() or "all"
        lens = _activity_scope_from_responsibility(
            request.user, space, responsibility,
        )
        if lens == set():
            raise NotFound()
        allowed_ids = _visible_activity_ids(request.user, space)
        if lens is not None:
            allowed_ids &= lens
        case = (
            service_journeys_visible_to(request.user)
            .filter(
                pk=journey_id, activity_id__in=allowed_ids,
                activity__space=space,
            )
            .select_related("activity", "service_context")
            .first()
        )
        if (
            case is None or
            service_case_scope(request.user, case) not in self._scopes or
            not hasattr(case, "service_context")
        ):
            raise NotFound()
        return space, responsibility, case

    @staticmethod
    def _offsets(request):
        values = {}
        for name in ("steps_offset", "blockers_offset"):
            try:
                offset = int(request.query_params.get(name, "0"))
            except (TypeError, ValueError):
                raise ValidationError({name: "Décalage invalide."})
            if not 0 <= offset <= 10000:
                raise ValidationError({name: "Décalage hors limites."})
            values[name] = offset
        return values

    def _projection(self, request, space, responsibility, case,
                    *, steps_offset=0, blockers_offset=0):
        context = case.service_context
        activity = case.activity
        can_manage = can(
            request.user, PermissionCode.ACTIVITY_SERVICES_CASES_MANAGE,
            activity=activity,
        )
        can_steps = can_manage and can(
            request.user, PermissionCode.ACTIVITY_SERVICES_STEPS_MANAGE,
            activity=activity,
        )
        can_blockers = can_manage and can(
            request.user, PermissionCode.ACTIVITY_SERVICES_BLOCKERS_MANAGE,
            activity=activity,
        )
        steps = list(
            case.steps.order_by("position", "pk")[
                steps_offset:steps_offset + 51
            ]
        )
        blockers = list(
            case.blockers.filter(status=JourneyBlockerStatus.ACTIVE)
            .order_by("-detected_at", "pk")[
                blockers_offset:blockers_offset + 51
            ]
        )
        assessments = (
            ServiceRequirementAssessment.objects.filter(context=context)
            .aggregate(
                total=Count("pk"),
                satisfied=Count(
                    "pk", filter=Q(status=RequirementAssessmentState.SATISFIED)
                ),
                awaiting=Count(
                    "pk", filter=Q(status__in=(
                        RequirementAssessmentState.UNASSESSED,
                        RequirementAssessmentState.PENDING,
                    ))
                ),
                unsatisfied=Count(
                    "pk", filter=Q(status=RequirementAssessmentState.UNSATISFIED)
                ),
            )
        )
        return {
            "space": {"id": str(space.pk), "slug": space.slug},
            "responsibility": responsibility,
            "owner": {"kind": "journey", "id": str(case.pk)},
            "activity": {"kind": "activity", "id": str(activity.pk),
                         "title": activity.title},
            "status": case.status,
            "objective": context.objective.strip() or None,
            "outcome": context.current_outcome,
            "conditions": {**assessments, "basis": "service_requirement_assessment"},
            "steps": [
                {
                    "id": str(step.pk), "title": step.title,
                    "kind": step.kind, "status": step.status,
                    "due_at": step.due_at.isoformat() if step.due_at else None,
                    "required": step.is_required,
                    # State and permissions are a hint, not transition proof.
                    "can_start": can_steps and step.status == JourneyStepStatus.READY,
                    "can_complete": can_steps and step.status == JourneyStepStatus.IN_PROGRESS,
                }
                for step in steps[:50]
            ],
            "steps_has_more": len(steps) > 50,
            "steps_page": {"offset": steps_offset, "limit": 50},
            "blockers": [
                {
                    "id": str(blocker.pk), "title": blocker.title,
                    "severity": blocker.severity, "status": blocker.status,
                    "step_id": str(blocker.step_id) if blocker.step_id else None,
                    "can_resolve": can_blockers,
                }
                for blocker in blockers[:50]
            ],
            "blockers_has_more": len(blockers) > 50,
            "blockers_page": {"offset": blockers_offset, "limit": 50},
            "capabilities": {
                "manage_steps": can_steps, "resolve_blockers": can_blockers,
            },
        }

    def get(self, request, slug, journey_id):
        space, responsibility, case = self._owner(request, slug, journey_id)
        offsets = self._offsets(request)
        return self._reply(self._projection(
            request, space, responsibility, case, **offsets,
        ))

    def post(self, request, slug, journey_id):
        space, responsibility, case = self._owner(request, slug, journey_id)
        offsets = self._offsets(request)
        data = request.data if isinstance(request.data, dict) else {}
        action = data.get("action")
        try:
            target_id = UUID(str(data.get("id", "")))
        except (TypeError, ValueError):
            raise ValidationError({"id": "Identifiant propriétaire invalide."})
        if action not in {"start_step", "complete_step", "resolve_blocker"}:
            raise ValidationError({"action": "Action inconnue."})

        can_manage = can(
            request.user, PermissionCode.ACTIVITY_SERVICES_CASES_MANAGE,
            activity=case.activity,
        )
        permission = (
            PermissionCode.ACTIVITY_SERVICES_BLOCKERS_MANAGE
            if action == "resolve_blocker"
            else PermissionCode.ACTIVITY_SERVICES_STEPS_MANAGE
        )
        if not can_manage or not can(request.user, permission, activity=case.activity):
            raise NotFound()

        try:
            if action == "resolve_blocker":
                blocker = JourneyBlocker.objects.filter(
                    pk=target_id, journey=case,
                    status=JourneyBlockerStatus.ACTIVE,
                ).first()
                if blocker is None:
                    raise NotFound()
                note = data.get("resolution_note", "")
                if not isinstance(note, str) or len(note) > 500:
                    raise ValidationError({"resolution_note": "Note invalide."})
                resolve_blocker(
                    blocker=blocker, actor=request.user,
                    resolution_note=note,
                )
            else:
                step = JourneyStep.objects.filter(
                    pk=target_id, journey=case,
                ).first()
                if step is None:
                    raise NotFound()
                if action == "start_step":
                    start_step(step=step, actor=request.user)
                else:
                    complete_step(step=step, actor=request.user)
        except (DjangoValidationError, DjangoPermissionDenied) as error:
            message = (
                "; ".join(error.messages)
                if hasattr(error, "messages") else str(error)
            )
            return self._reply({"detail": message}, status=409)
        # Read the owner fresh after a confirmed transition; do not trust
        # optimistic local state.
        case.refresh_from_db()
        return self._reply({
            **self._projection(request, space, responsibility, case, **offsets),
            "confirmed_by_owner": True,
        })
