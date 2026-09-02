from __future__ import annotations

from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from journeys.collaboration_models import (
    JourneyStep,
    JourneyStepDependency,
    JourneyStepOrigin,
    JourneyStepStatus,
)

from .models import (
    ServiceJourneyContext,
    ServicePlanMaterialization,
    ServicePlanTemplate,
    ServicePlanTemplateStatus,
    ServicePlanTemplateStepDependency,
)
from .services import create_service_journey


@transaction.atomic
def create_reused_service_journey(
    *,
    source_journey,
    recipient,
    template,
    opportunity=None,
    opportunity_revision=None,
):
    """Create and prepare a fresh Service Journey from current canonical sources.

    This is a trusted Services-domain materializer for a newly created recipient-owned
    Journey. It deliberately does not call operator-facing Journey mutation services:
    those services require an explicit Services operator and their authorization must
    not be weakened merely to support Sharing.

    No source Journey state, assignment, blocker, artifact, answer, outcome, payment,
    access or validation is read or transferred here.
    """

    service = source_journey.activity.service_details
    template = (
        ServicePlanTemplate.objects.select_for_update(of=("self",))
        .select_related("service", "service__activity")
        .get(pk=template.pk)
    )
    if template.service_id != service.pk or template.status != ServicePlanTemplateStatus.PUBLISHED:
        raise ValidationError("Le plan réutilisable n’est plus disponible dans sa version canonique actuelle.")

    journey = create_service_journey(
        service=service,
        initiated_by=recipient,
        beneficiary=recipient,
        objective="",
        template=template,
        opportunity=opportunity,
        opportunity_revision=opportunity_revision,
    )
    context = ServiceJourneyContext.objects.select_for_update(of=("self",)).get(journey=journey)

    template_steps = list(template.steps.all().order_by("position", "created_at", "id"))
    if not template_steps:
        raise ValidationError("Le plan Services ne contient aucune étape réutilisable.")

    dependencies = list(
        ServicePlanTemplateStepDependency.objects.filter(step__template=template)
        .select_related("step", "depends_on")
        .order_by("created_at", "id")
    )
    dependent_ids = {dependency.step_id for dependency in dependencies}

    mapping = {}
    now = timezone.now()
    for template_step in template_steps:
        due_at = (
            now + timedelta(days=template_step.relative_due_days)
            if template_step.relative_due_days is not None
            else None
        )
        step = JourneyStep(
            journey=journey,
            title=template_step.title,
            kind=template_step.kind,
            description=template_step.description,
            status=(
                JourneyStepStatus.PENDING
                if template_step.pk in dependent_ids
                else JourneyStepStatus.READY
            ),
            position=template_step.position,
            is_required=template_step.is_required,
            due_at=due_at,
            origin=JourneyStepOrigin.TEMPLATE,
            created_by=None,
            status_reason=(
                ""
                if template_step.pk in dependent_ids
                else "journey_reuse_materialized"
            ),
        )
        step.save()
        mapping[template_step.pk] = step
        ServicePlanMaterialization.objects.create(
            context=context,
            template_step=template_step,
            journey_step=step,
        )

    for dependency in dependencies:
        JourneyStepDependency.objects.create(
            step=mapping[dependency.step_id],
            depends_on=mapping[dependency.depends_on_id],
        )

    context.plan_materialized_at = now
    context.save(update_fields=["plan_materialized_at", "updated_at"])
    return journey
