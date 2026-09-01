from .registry import registry
from .types import NextAction, ReadinessCheck, ReadinessCheckState


@registry.register
def questionnaire_contributor(journey, viewer, now):
    checks = []
    requests = list(journey.form_requests.all())
    for request in requests:
        if not request.required or request.status == "cancelled":
            continue
        key = f"form_request.{request.pk}"
        response = getattr(request, "response", None)
        if request.status == "completed" and response is not None and response.status == "submitted":
            checks.append(
                ReadinessCheck(
                    key=key,
                    source="questionnaire",
                    state=ReadinessCheckState.SATISFIED,
                    blocking=False,
                    reason_code="form_response_submitted",
                    summary=request.form_version.title,
                )
            )
            continue
        if request.opens_at and now < request.opens_at:
            checks.append(
                ReadinessCheck(
                    key=key,
                    source="questionnaire",
                    state=ReadinessCheckState.WAITING,
                    blocking=False,
                    reason_code="form_response_not_open",
                    summary=request.form_version.title,
                )
            )
            continue
        if request.due_at and now > request.due_at:
            checks.append(
                ReadinessCheck(
                    key=key,
                    source="questionnaire",
                    state=ReadinessCheckState.BLOCKING,
                    blocking=True,
                    reason_code="form_response_deadline_passed",
                    summary=request.form_version.title,
                )
            )
            continue
        action = NextAction(
            key="complete_form",
            label=f"Compléter « {request.form_version.title} »",
            url=f"/questionnaires/requests/{request.pk}/",
            source="questionnaire",
        )
        checks.append(
            ReadinessCheck(
                key=key,
                source="questionnaire",
                state=ReadinessCheckState.ACTION_REQUIRED,
                blocking=False,
                reason_code="form_response_required",
                summary=request.form_version.title,
                next_action=action,
            )
        )
    if not checks:
        checks.append(
            ReadinessCheck(
                key="questionnaires",
                source="questionnaire",
                state=ReadinessCheckState.NOT_APPLICABLE,
                blocking=False,
                reason_code="forms_satisfied_or_not_applicable",
                summary="Aucun formulaire obligatoire en attente.",
            )
        )
    return checks
