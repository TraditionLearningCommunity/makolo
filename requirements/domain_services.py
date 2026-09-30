from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from authorization.constants import PermissionCode
from authorization.services import can

from .contracts import RequirementAssessmentState
from .models import (
    JourneyRequirementAssessment,
    RequirementDefinition,
    RequirementDefinitionStatus,
)
from .registry import registry


def _require_manage(actor, activity):
    if not getattr(actor, "is_authenticated", False) or not can(
        actor, PermissionCode.ACTIVITY_MANAGE, activity=activity
    ):
        raise PermissionDenied("Une autorité Activity de gestion est requise.")


@transaction.atomic
def create_requirement_definition(
    *,
    activity,
    key,
    title,
    actor,
    description="",
    mode="verification",
    evaluator_key="",
    evaluator_config=None,
    is_mandatory=True,
    position=0,
):
    _require_manage(actor, activity)
    latest = (
        RequirementDefinition.objects.select_for_update()
        .filter(activity=activity, key=key)
        .order_by("-version")
        .first()
    )
    requirement = RequirementDefinition(
        activity=activity,
        key=key,
        version=(latest.version + 1) if latest else 1,
        title=title,
        description=description,
        mode=mode,
        evaluator_key=evaluator_key,
        evaluator_config=evaluator_config or {},
        is_mandatory=is_mandatory,
        position=position,
        created_by=actor,
    )
    requirement.save()
    return requirement


@transaction.atomic
def publish_requirement_definition(*, requirement, actor):
    requirement = (
        RequirementDefinition.objects.select_for_update()
        .select_related("activity")
        .get(pk=requirement.pk)
    )
    _require_manage(actor, requirement.activity)
    if requirement.status == RequirementDefinitionStatus.PUBLISHED:
        return requirement
    if requirement.status != RequirementDefinitionStatus.DRAFT:
        raise ValidationError("Seul un Requirement brouillon peut être publié.")
    now = timezone.now()
    previous = (
        RequirementDefinition.objects.select_for_update()
        .filter(
            activity=requirement.activity,
            key=requirement.key,
            status=RequirementDefinitionStatus.PUBLISHED,
        )
        .exclude(pk=requirement.pk)
        .first()
    )
    if previous:
        previous.status = RequirementDefinitionStatus.RETIRED
        previous.retired_at = now
        previous.save(update_fields=["status", "retired_at", "updated_at"])
    requirement.status = RequirementDefinitionStatus.PUBLISHED
    requirement.published_at = now
    requirement.save(update_fields=["status", "published_at", "updated_at"])
    return requirement


@transaction.atomic
def create_journey_requirement_assessment(
    *,
    journey,
    requirement,
    journey_step=None,
):
    if requirement.status != RequirementDefinitionStatus.PUBLISHED:
        raise ValidationError("Le Requirement doit être publié.")
    if requirement.activity_id != journey.activity_id:
        raise ValidationError("Le Requirement appartient à une autre Activity.")
    if journey_step is not None and journey_step.journey_id != journey.pk:
        raise ValidationError("La Step de satisfaction appartient à une autre Journey.")
    assessment, created = JourneyRequirementAssessment.objects.get_or_create(
        journey=journey,
        requirement=requirement,
        defaults={"journey_step": journey_step},
    )
    if not created and assessment.journey_step_id != getattr(journey_step, "pk", None):
        raise ValidationError("L'Assessment existe déjà avec une autre Step de satisfaction.")
    return assessment


def _save_assessment(
    assessment,
    *,
    state,
    actor=None,
    reason_code="",
    note="",
    observed_at=None,
):
    assessment.state = state
    assessment.reason_code = (reason_code or "")[:160]
    assessment.note = note or ""
    assessment.observed_at = observed_at or timezone.now()
    assessment.assessed_at = timezone.now()
    assessment.assessed_by = actor if getattr(actor, "is_authenticated", False) else None
    assessment._allow_state_transition = True
    assessment.save()
    return assessment


@transaction.atomic
def assess_journey_requirement(
    *,
    assessment,
    actor,
    state,
    reason_code="human_assessment",
    note="",
):
    assessment = (
        JourneyRequirementAssessment.objects.select_for_update()
        .select_related("journey__activity", "requirement")
        .get(pk=assessment.pk)
    )
    _require_manage(actor, assessment.journey.activity)
    if state not in RequirementAssessmentState.values:
        raise ValidationError({"state": "État Requirement inconnu."})
    return _save_assessment(
        assessment,
        state=state,
        actor=actor,
        reason_code=reason_code,
        note=note,
    )


@transaction.atomic
def evaluate_journey_requirement(*, assessment, subject=None):
    assessment = (
        JourneyRequirementAssessment.objects.select_for_update()
        .select_related("journey__beneficiary", "requirement")
        .get(pk=assessment.pk)
    )
    requirement = assessment.requirement
    if not requirement.evaluator_key:
        raise ValidationError("Ce Requirement ne possède aucun evaluator automatique.")
    subject = subject if subject is not None else assessment.journey.beneficiary
    result = registry.evaluate(
        requirement.evaluator_key,
        subject=subject,
        config=requirement.evaluator_config,
    )
    return _save_assessment(
        assessment,
        state=result.state,
        reason_code=result.reason_code,
        observed_at=result.observed_at,
    )
