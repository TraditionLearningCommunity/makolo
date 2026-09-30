from datetime import timedelta

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from authorization.constants import PermissionCode
from authorization.services import can

from .collaboration_models import (
    JourneyPlanMaterialization,
    JourneyPlanStepActor,
    JourneyPlanTemplate,
    JourneyPlanTemplateStatus,
    JourneyPlanTemplateStep,
    JourneyPlanTemplateStepDependency,
    JourneyAssignment,
    JourneyStep,
    JourneyStepAssignment,
    JourneyAssignmentResponsibility,
    JourneyAssignmentStatus,
    JourneyStepOrigin,
    JourneyStepStatus,
)
from .collaboration_services import mark_ready


def _require_manage(actor, activity):
    if not getattr(actor, "is_authenticated", False) or not can(
        actor, PermissionCode.ACTIVITY_MANAGE, activity=activity
    ):
        raise PermissionDenied("Une autorité Activity de gestion est requise.")


@transaction.atomic
def create_journey_plan_template(
    *,
    activity,
    key,
    name,
    steps,
    actor,
):
    _require_manage(actor, activity)
    steps = list(steps)
    if not steps:
        raise ValidationError({"steps": "Un plan publié doit contenir au moins une étape."})
    latest = (
        JourneyPlanTemplate.objects.select_for_update()
        .filter(activity=activity, key=key)
        .order_by("-version")
        .first()
    )
    template = JourneyPlanTemplate.objects.create(
        activity=activity,
        key=key,
        version=(latest.version + 1) if latest else 1,
        name=name,
        created_by=actor,
    )
    by_key = {}
    pending_dependencies = []
    for position, item in enumerate(steps):
        step_key = (item.get("key") or f"step-{position + 1}").strip()
        if step_key in by_key:
            raise ValidationError({"steps": f"Clé d'étape dupliquée : {step_key}."})
        step = JourneyPlanTemplateStep.objects.create(
            template=template,
            key=step_key,
            kind=item.get("kind", "action"),
            actor_kind=item.get("actor_kind", JourneyPlanStepActor.BENEFICIARY),
            title=item["title"],
            description=item.get("description", ""),
            position=item.get("position", position),
            is_required=item.get("is_required", True),
            relative_due_days=item.get("relative_due_days"),
        )
        by_key[step_key] = step
        pending_dependencies.append((step, list(item.get("depends_on", []))))
    for step, dependency_keys in pending_dependencies:
        for dependency_key in dependency_keys:
            dependency = by_key.get(dependency_key)
            if dependency is None:
                raise ValidationError(
                    {"steps": f"Dépendance inconnue « {dependency_key} » pour {step.key}."}
                )
            JourneyPlanTemplateStepDependency.objects.create(
                step=step,
                depends_on=dependency,
            )
    return template


@transaction.atomic
def publish_journey_plan_template(*, template, actor):
    template = (
        JourneyPlanTemplate.objects.select_for_update()
        .select_related("activity")
        .prefetch_related("steps")
        .get(pk=template.pk)
    )
    _require_manage(actor, template.activity)
    if template.status == JourneyPlanTemplateStatus.PUBLISHED:
        return template
    if template.status != JourneyPlanTemplateStatus.DRAFT:
        raise ValidationError("Seul un plan Journey brouillon peut être publié.")
    if not template.steps.exists():
        raise ValidationError("Un plan Journey publié doit contenir au moins une étape.")
    now = timezone.now()
    previous = (
        JourneyPlanTemplate.objects.select_for_update()
        .filter(
            activity=template.activity,
            key=template.key,
            status=JourneyPlanTemplateStatus.PUBLISHED,
        )
        .exclude(pk=template.pk)
        .first()
    )
    if previous:
        previous.status = JourneyPlanTemplateStatus.RETIRED
        previous.retired_at = now
        previous.save(update_fields=["status", "retired_at", "updated_at"])
    template.status = JourneyPlanTemplateStatus.PUBLISHED
    template.published_at = now
    template.save(update_fields=["status", "published_at", "updated_at"])
    return template


def _can_materialize(actor, journey):
    if not getattr(actor, "is_authenticated", False):
        return False
    if journey.beneficiary_id == getattr(actor, "pk", None):
        return True
    return can(actor, PermissionCode.ACTIVITY_MANAGE, activity=journey.activity)


@transaction.atomic
def materialize_journey_plan(*, journey, template, actor):
    journey = (
        journey.__class__.objects.select_for_update()
        .select_related("activity", "beneficiary")
        .get(pk=journey.pk)
    )
    template = (
        JourneyPlanTemplate.objects.select_for_update()
        .select_related("activity", "created_by")
        .prefetch_related("steps__dependencies__depends_on")
        .get(pk=template.pk)
    )
    if not _can_materialize(actor, journey):
        raise PermissionDenied("Vous ne pouvez pas matérialiser ce plan.")
    if template.status != JourneyPlanTemplateStatus.PUBLISHED:
        raise ValidationError("Le plan Journey doit être publié.")
    if template.activity_id != journey.activity_id:
        raise ValidationError("Le plan Journey appartient à une autre Activity.")

    existing = list(
        JourneyPlanMaterialization.objects.filter(journey=journey)
        .select_related("journey_step", "template_step")
        .order_by("template_step__position", "created_at")
    )
    if existing:
        if any(row.template_step.template_id != template.pk for row in existing):
            raise ValidationError("Cette Journey a déjà matérialisé un autre plan.")
        return [row.journey_step for row in existing]

    template_steps = list(template.steps.all())
    if not template_steps:
        raise ValidationError("Le plan Journey ne contient aucune étape.")

    now = timezone.now()
    mapping = {}
    for template_step in template_steps:
        due_at = (
            now + timedelta(days=template_step.relative_due_days)
            if template_step.relative_due_days is not None
            else None
        )
        created_by = (
            journey.beneficiary
            if template_step.actor_kind == JourneyPlanStepActor.BENEFICIARY
            else template.created_by
        )
        step = JourneyStep.objects.create(
            journey=journey,
            kind=template_step.kind,
            title=template_step.title,
            description=template_step.description,
            position=template_step.position,
            is_required=template_step.is_required,
            due_at=due_at,
            origin=JourneyStepOrigin.TEMPLATE,
            created_by=created_by,
        )
        mapping[template_step.pk] = step
        JourneyPlanMaterialization.objects.create(
            journey=journey,
            template_step=template_step,
            journey_step=step,
        )
        if (
            template_step.actor_kind == JourneyPlanStepActor.OPERATOR
            and template.created_by_id
        ):
            JourneyAssignment.objects.get_or_create(
                journey=journey,
                profile=template.created_by,
                responsibility=JourneyAssignmentResponsibility.LEAD,
                status=JourneyAssignmentStatus.ACTIVE,
                defaults={
                    "is_primary": False,
                    "assigned_by": template.created_by,
                },
            )
            JourneyStepAssignment.objects.create(
                step=step,
                profile=template.created_by,
                responsibility=JourneyAssignmentResponsibility.LEAD,
                status=JourneyAssignmentStatus.ACTIVE,
                assigned_by=template.created_by,
            )

    for template_step in template_steps:
        for dependency in template_step.dependencies.all():
            from .collaboration_models import JourneyStepDependency

            JourneyStepDependency.objects.create(
                step=mapping[template_step.pk],
                depends_on=mapping[dependency.depends_on_id],
            )

    for step in mapping.values():
        if step.status == JourneyStepStatus.PENDING and not step.dependencies.exists():
            mark_ready(step=step, actor=None, reason="journey_plan_materialized")
    return [mapping[row.pk] for row in template_steps]
