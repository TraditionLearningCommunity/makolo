from journeys.collaboration_models import JourneyStepStatus
from readiness.registry import registry
from readiness.types import ReadinessCheck, ReadinessCheckState

from .contracts import RequirementAssessmentState, RequirementMode


@registry.register
def generic_requirements_contributor(journey, viewer, now):
    assessments = list(journey.requirement_assessments.all())
    if not assessments:
        return []
    checks = []
    for assessment in assessments:
        requirement = assessment.requirement
        if not requirement.is_mandatory:
            continue
        key = f"generic_requirement.{assessment.pk}"
        state = assessment.state
        if (
            state == RequirementAssessmentState.UNASSESSED
            and requirement.mode == RequirementMode.ACTION
            and assessment.journey_step_id
            and assessment.journey_step.status == JourneyStepStatus.COMPLETED
        ):
            state = RequirementAssessmentState.SATISFIED

        if state == RequirementAssessmentState.SATISFIED:
            readiness_state = ReadinessCheckState.SATISFIED
            blocking = False
            reason = "requirement_satisfied"
        elif state == RequirementAssessmentState.NOT_APPLICABLE:
            readiness_state = ReadinessCheckState.NOT_APPLICABLE
            blocking = False
            reason = "requirement_not_applicable"
        elif state in {
            RequirementAssessmentState.UNASSESSED,
            RequirementAssessmentState.PENDING,
        }:
            readiness_state = ReadinessCheckState.WAITING
            blocking = False
            reason = (
                "requirement_unassessed"
                if state == RequirementAssessmentState.UNASSESSED
                else "requirement_pending"
            )
        else:
            readiness_state = ReadinessCheckState.BLOCKING
            blocking = True
            reason = "requirement_unsatisfied"
        checks.append(
            ReadinessCheck(
                key=key,
                source="requirements",
                state=readiness_state,
                blocking=blocking,
                reason_code=reason,
                summary=requirement.title,
            )
        )
    return checks
