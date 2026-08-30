from django import template

from journeys.models import WorkflowKind

from services.requirement_services import derive_requirement_consequence
from services.selectors import service_artifacts_visible_to, service_notes_visible_to, submissions_for_context, outcome_timeline

register = template.Library()


CONSEQUENCE_LABELS = {
    "action_required": "Action requise",
    "needs_review": "En revue",
    "payment_required": "Paiement requis",
    "not_eligible": "Condition non satisfaite",
}


def _payee_label(obligation):
    if obligation.external_payee_name:
        return obligation.external_payee_name
    if obligation.payee_space_id:
        return obligation.payee_space.name
    if obligation.payee_profile_id:
        return obligation.payee_profile.full_name or obligation.payee_profile.username
    return ""


def _timeline(context, steps, artifacts, notes, obligations, submissions, outcomes):
    rows = []
    journey = context.journey
    rows.append({"at": journey.created_at, "label": "Démarche créée", "kind": "journey"})
    for step in steps:
        at = step.completed_at or step.started_at or step.created_at
        rows.append({"at": at, "label": f"Étape · {step.title} · {step.get_status_display()}", "kind": "step"})
    for artifact in artifacts:
        rows.append({"at": artifact.created_at, "label": f"Document · {artifact.title} · version {artifact.version}", "kind": "artifact"})
        for review in artifact.reviews.all():
            rows.append({"at": review.decided_at or review.started_at or review.created_at, "label": f"Revue · {review.get_status_display()}", "kind": "review"})
    for obligation in obligations:
        rows.append({"at": obligation.created_at, "label": f"Paiement requis · {obligation.label}", "kind": "payment"})
        for evidence in obligation.evidence.all():
            rows.append({"at": evidence.verified_at or evidence.created_at, "label": f"Preuve de paiement · {evidence.get_status_display()}", "kind": "payment_evidence"})
    for note in notes:
        rows.append({"at": note.created_at, "label": "Note ajoutée", "kind": "note"})
    for submission in submissions:
        rows.append({"at": submission.submitted_at or submission.created_at, "label": f"Soumission externe · {submission.get_status_display()}", "kind": "submission"})
    for outcome in outcomes:
        rows.append({"at": outcome.occurred_at, "label": f"Résultat externe · {outcome.get_event_type_display()}", "kind": "outcome"})
    return sorted((row for row in rows if row["at"] is not None), key=lambda row: row["at"], reverse=True)[:40]


@register.inclusion_tag("services/participant_workspace.html", takes_context=True)
def service_participant_workspace(context, journey):
    request = context.get("request")
    actor = getattr(request, "user", None)
    if journey.workflow != WorkflowKind.SERVICE or actor is None or journey.beneficiary_id != getattr(actor, "pk", None):
        return {"is_service_workspace": False}

    try:
        service_context = journey.service_context
    except Exception:
        return {"is_service_workspace": False}

    assessments = list(
        service_context.requirement_assessments.select_related("requirement")
        .prefetch_related("step_links__journey_step", "payment_obligation_links__obligation", "evidence")
        .order_by("requirement__position", "created_at", "id")
    )
    requirement_rows = []
    for assessment in assessments:
        consequence = derive_requirement_consequence(assessment)
        requirement_rows.append({
            "assessment": assessment,
            "requirement": assessment.requirement,
            "consequence": consequence.value if consequence else "",
            "consequence_label": CONSEQUENCE_LABELS.get(consequence.value, "") if consequence else "",
            "steps": [link.journey_step for link in assessment.step_links.all()],
        })

    steps = list(
        journey.steps.select_related("occurrence")
        .prefetch_related("dependencies__depends_on", "blockers")
        .order_by("position", "created_at", "id")
    )
    blockers = list(journey.blockers.select_related("step", "responsible_profile").order_by("status", "-severity", "due_at", "created_at", "id"))
    artifacts = list(service_artifacts_visible_to(actor, journey=journey).prefetch_related("reviews").order_by("step__position", "created_at", "id"))
    notes = list(service_notes_visible_to(actor, journey=journey).order_by("-created_at", "-id"))
    obligations = list(
        journey.payment_obligations.select_related("step", "payee_space", "payee_profile")
        .prefetch_related("evidence")
        .order_by("status", "due_at", "created_at", "id")
    )
    for obligation in obligations:
        obligation.participant_payee_label = _payee_label(obligation)
    submissions = list(submissions_for_context(service_context))
    outcomes = list(outcome_timeline(service_context))

    required_steps = [step for step in steps if step.is_required]
    completed_required = [step for step in required_steps if step.status in {"completed", "skipped"}]
    required_requirements = [row for row in requirement_rows if row["requirement"].is_mandatory]
    satisfied_requirements = [row for row in required_requirements if row["assessment"].status in {"satisfied", "not_applicable"}]
    next_step = next((step for step in steps if step.status in {"ready", "in_progress", "blocked"}), None)
    next_requirement = next((row for row in requirement_rows if row["consequence_label"]), None)
    next_action = next_requirement["consequence_label"] if next_requirement else (next_step.title if next_step else "Aucune action immédiate")

    return {
        "is_service_workspace": True,
        "journey": journey,
        "service_context": service_context,
        "service_details": journey.activity.service_details,
        "requirements": requirement_rows,
        "steps": steps,
        "blockers": blockers,
        "artifacts": artifacts,
        "notes": notes,
        "obligations": obligations,
        "submissions": submissions,
        "outcomes": outcomes,
        "timeline": _timeline(service_context, steps, artifacts, notes, obligations, submissions, outcomes),
        "required_steps_count": len(required_steps),
        "completed_required_steps_count": len(completed_required),
        "required_requirements_count": len(required_requirements),
        "satisfied_requirements_count": len(satisfied_requirements),
        "next_action": next_action,
        "next_step": next_step,
    }
