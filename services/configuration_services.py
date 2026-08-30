from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from authorization.constants import PermissionCode
from authorization.services import can

from .models import ServiceDetails, ServiceIntakeQuestion


def _ensure_configure(actor, service):
    if not getattr(actor, "is_authenticated", False) or not can(
        actor,
        PermissionCode.ACTIVITY_SERVICES_CONFIGURE,
        activity=service.activity,
    ):
        raise PermissionDenied("La configuration de ce Service n'est pas autorisée.")


@transaction.atomic
def update_service_details(
    *,
    service,
    actor,
    service_kind,
    opportunity_policy,
    intake_policy,
    allows_external_beneficiary,
    completion_policy,
):
    service = (
        ServiceDetails.objects.select_for_update(of=("self",))
        .select_related("activity")
        .order_by()
        .get(pk=service.pk)
    )
    _ensure_configure(actor, service)
    service.service_kind = service_kind
    service.opportunity_policy = opportunity_policy
    service.intake_policy = intake_policy
    service.allows_external_beneficiary = bool(allows_external_beneficiary)
    service.completion_policy = completion_policy
    service.full_clean()
    service.save(
        update_fields=[
            "service_kind",
            "opportunity_policy",
            "intake_policy",
            "allows_external_beneficiary",
            "completion_policy",
            "updated_at",
        ]
    )
    return service


@transaction.atomic
def create_intake_question(
    *,
    service,
    actor,
    key,
    prompt,
    question_type,
    options=None,
    is_required=False,
    position=0,
    template=None,
):
    service = ServiceDetails.objects.select_related("activity").get(pk=service.pk)
    _ensure_configure(actor, service)
    if template is not None:
        template = template.__class__.objects.select_related("service").get(pk=template.pk)
        if template.service_id != service.pk:
            raise ValidationError("La question Intake doit utiliser un template de ce Service.")
    question = ServiceIntakeQuestion(
        service=None if template is not None else service,
        template=template,
        key=(key or "").strip(),
        prompt=(prompt or "").strip(),
        question_type=question_type,
        options=list(options or []),
        is_required=bool(is_required),
        position=position,
    )
    question.save()
    return question
