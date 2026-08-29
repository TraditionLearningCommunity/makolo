from authorization.constants import SystemRoleCode
from authorization.models import AuthorityScope, Mandate, MandateStatus
from journeys.collaboration_models import JourneyArtifactReviewStatus, JourneyArtifactSensitivity, JourneyAssignmentStatus, JourneyNoteVisibility
from journeys.models import Journey, WorkflowKind
from payments.models import PaymentEvidenceStatus

from .common import stable_uuid
from .task34b_extension import T34B_PERSONAS


def assert_task34b_beta_coverage() -> dict[str, int]:
    missing = []
    for key, email in T34B_PERSONAS.items():
        from accounts.models import User
        if not User.objects.filter(email=email, is_active=True).exists():
            missing.append(f"persona:{key}")
    expected_roles = {
        "service_manager": SystemRoleCode.ACTIVITY_SERVICE_MANAGER,
        "service_facilitator": SystemRoleCode.ACTIVITY_SERVICE_FACILITATOR,
        "service_reviewer": SystemRoleCode.ACTIVITY_SERVICE_REVIEWER,
    }
    for key, role_code in expected_roles.items():
        if not Mandate.objects.filter(
            profile__email=T34B_PERSONAS[key],
            scope_type=AuthorityScope.ACTIVITY,
            role__code=role_code,
            status=MandateStatus.ACTIVE,
        ).exists():
            missing.append(f"mandate:{key}")
    if not Mandate.objects.filter(
        profile__email=T34B_PERSONAS["opportunity_curator"],
        scope_type=AuthorityScope.PLATFORM,
        role__code=SystemRoleCode.OPPORTUNITY_CURATOR,
        status=MandateStatus.ACTIVE,
    ).exists():
        missing.append("mandate:opportunity_curator")

    assigned = Journey.objects.filter(pk=stable_uuid("task34b-service-journey-assigned"), workflow=WorkflowKind.SERVICE).first()
    unassigned = Journey.objects.filter(pk=stable_uuid("task34b-service-journey-unassigned"), workflow=WorkflowKind.SERVICE).first()
    if assigned is None:
        missing.append("journey:assigned")
    if unassigned is None:
        missing.append("journey:unassigned")
    if assigned is not None:
        if not assigned.assignments.filter(status=JourneyAssignmentStatus.ACTIVE).exists():
            missing.append("assignment:active")
        if not assigned.artifacts.filter(sensitivity=JourneyArtifactSensitivity.RESTRICTED).exists():
            missing.append("artifact:restricted")
        if not assigned.artifacts.filter(reviews__status=JourneyArtifactReviewStatus.REQUESTED).exists():
            missing.append("review:requested")
        if not assigned.notes.filter(visibility=JourneyNoteVisibility.INTERNAL).exists():
            missing.append("note:internal")
        if not assigned.payment_obligations.filter(evidence__status=PaymentEvidenceStatus.SUBMITTED).exists():
            missing.append("payment_evidence:submitted")
        context = getattr(assigned, "service_context", None)
        if context is None or not context.opportunity_revision_id or not context.opportunity_id:
            missing.append("opportunity:pinned")
        elif context.opportunity.current_revision_id == context.opportunity_revision_id:
            missing.append("opportunity:newer_revision")
        elif not context.opportunity.sources.filter(status="changed").exists():
            missing.append("opportunity:source_changed")
    if missing:
        raise AssertionError("T34B beta seed incomplet: " + ", ".join(missing))
    return {
        "t34b_personas": len(T34B_PERSONAS),
        "t34b_service_journeys": 2,
        "t34b_restricted_artifacts": 1,
        "t34b_requested_reviews": 1,
        "t34b_submitted_payment_evidence": 1,
        "t34b_newer_opportunity_revision": 1,
        "t34b_changed_opportunity_source": 1,
    }
