from __future__ import annotations

from datetime import timedelta

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from authorization.constants import PermissionCode
from authorization.services import can
from journeys.beneficiary_services import create_journey_for_holder
from journeys.collaboration_models import (
    JourneyArtifactReviewStatus,
    JourneyBlockerSeverity,
    JourneyBlockerStatus,
    JourneyStepKind,
    JourneyStepOrigin,
    JourneyStepStatus,
)
from journeys.collaboration_services import add_step_dependency, create_step, ensure_case_access, is_beneficiary, mark_ready
from journeys.models import JourneyStatus, WorkflowKind
from journeys.services import _fulfill_service_journey, confirm_journey, create_request, start_journey, submit_journey

from .models import (
    CompletionPolicy,
    IntakePolicy,
    OpportunityPolicy,
    ServiceDetails,
    ServiceIntakeAnswer,
    ServiceIntakeQuestion,
    ServiceJourneyContext,
    ServicePlanMaterialization,
    ServicePlanTemplate,
    ServicePlanTemplateStatus,
    ServicePlanTemplateStep,
    ServicePlanTemplateStepDependency,
)
from .requirement_services import (
    adopt_opportunity_revision,
    assess_requirement,
    attach_opportunity_to_service_journey,
    create_requirement_step,
    ensure_requirement_assessments,
    has_newer_opportunity_revision,
    link_requirement_step,
    requirement_progress,
    resolve_opportunity_selection,
    review_requirement_evidence,
    submit_requirement_evidence,
    validate_requirement_completion,
)


def _ensure_activity_manager(actor, service):
    if not getattr(actor, "is_authenticated", False) or not can(actor, PermissionCode.ACTIVITY_MANAGE, activity=service.activity):
        raise PermissionDenied("Une autorité Activity de gestion est requise pour configurer ce Service.")


def create_service_details(*, activity, actor, service_kind, opportunity_policy=OpportunityPolicy.NONE, intake_policy=IntakePolicy.AUTO_CONFIRM, allows_external_beneficiary=False, completion_policy=CompletionPolicy.REQUIRED_STEPS):
    if not can(actor, PermissionCode.ACTIVITY_MANAGE, activity=activity):
        raise PermissionDenied("Vous ne pouvez pas spécialiser cette Activity en Service.")
    service = ServiceDetails(activity=activity, service_kind=service_kind, opportunity_policy=opportunity_policy, intake_policy=intake_policy, allows_external_beneficiary=allows_external_beneficiary, completion_policy=completion_policy)
    service.full_clean()
    service.save()
    return service


@transaction.atomic
def create_plan_template(*, service, actor, key, name, version=1):
    _ensure_activity_manager(actor, service)
    template = ServicePlanTemplate(service=service, key=(key or "").strip(), name=(name or "").strip(), version=version, created_by=actor)
    template.save()
    return template


@transaction.atomic
def add_template_step(*, template, actor, title, kind=JourneyStepKind.ACTION, description="", position=0, is_required=True, relative_due_days=None):
    template = (
        ServicePlanTemplate.objects.select_for_update(of=("self",))
        .select_related("service", "service__activity")
        .order_by()
        .get(pk=template.pk)
    )
    _ensure_activity_manager(actor, template.service)
    if template.status != ServicePlanTemplateStatus.DRAFT:
        raise ValidationError("Seul un template brouillon peut être modifié.")
    step = ServicePlanTemplateStep(template=template, title=(title or "").strip(), kind=kind, description=description or "", position=position, is_required=is_required, relative_due_days=relative_due_days)
    step.save()
    return step


def _template_dependency_would_cycle(*, step, depends_on):
    frontier = {depends_on.pk}
    visited = set()
    while frontier:
        if step.pk in frontier:
            return True
        visited.update(frontier)
        frontier = set(ServicePlanTemplateStepDependency.objects.filter(step_id__in=frontier).exclude(depends_on_id__in=visited).values_list("depends_on_id", flat=True))
    return False


@transaction.atomic
def add_template_dependency(*, step, depends_on, actor):
    step = ServicePlanTemplateStep.objects.select_related("template", "template__service", "template__service__activity").get(pk=step.pk)
    depends_on = ServicePlanTemplateStep.objects.select_related("template").get(pk=depends_on.pk)
    if step.template_id != depends_on.template_id:
        raise ValidationError("Une dépendance de plan ne peut pas traverser deux templates.")
    template = (
        ServicePlanTemplate.objects.select_for_update(of=("self",))
        .select_related("service", "service__activity")
        .order_by()
        .get(pk=step.template_id)
    )
    _ensure_activity_manager(actor, template.service)
    if template.status != ServicePlanTemplateStatus.DRAFT:
        raise ValidationError("Un template publié ou retiré est immuable.")
    if step.pk == depends_on.pk:
        raise ValidationError("Une étape de plan ne peut pas dépendre d’elle-même.")
    if ServicePlanTemplateStepDependency.objects.filter(step=step, depends_on=depends_on).exists():
        raise ValidationError("Cette dépendance de plan existe déjà.")
    if _template_dependency_would_cycle(step=step, depends_on=depends_on):
        raise ValidationError("Cette dépendance de plan créerait un cycle.")
    dependency = ServicePlanTemplateStepDependency(step=step, depends_on=depends_on)
    dependency.save()
    return dependency


@transaction.atomic
def publish_plan_template(*, template, actor):
    template = ServicePlanTemplate.objects.select_for_update(of=("self",)).select_related("service", "service__activity").order_by().get(pk=template.pk)
    _ensure_activity_manager(actor, template.service)
    if template.status == ServicePlanTemplateStatus.PUBLISHED:
        return template
    if template.status != ServicePlanTemplateStatus.DRAFT:
        raise ValidationError("Seul un template brouillon peut être publié.")
    if not template.steps.exists():
        raise ValidationError("Un plan Services publié doit contenir au moins une étape.")
    template.status = ServicePlanTemplateStatus.PUBLISHED
    template.save(update_fields=["status", "updated_at"])
    return template


@transaction.atomic
def retire_plan_template(*, template, actor):
    template = ServicePlanTemplate.objects.select_for_update(of=("self",)).select_related("service", "service__activity").order_by().get(pk=template.pk)
    _ensure_activity_manager(actor, template.service)
    if template.status == ServicePlanTemplateStatus.RETIRED:
        return template
    if template.status != ServicePlanTemplateStatus.PUBLISHED:
        raise ValidationError("Seul un template publié peut être retiré.")
    template.status = ServicePlanTemplateStatus.RETIRED
    template.save(update_fields=["status", "updated_at"])
    return template


@transaction.atomic
def create_plan_template_version(*, template, actor, name=None):
    template = ServicePlanTemplate.objects.select_for_update(of=("self",)).prefetch_related("steps__dependencies").select_related("service", "service__activity").order_by().get(pk=template.pk)
    _ensure_activity_manager(actor, template.service)
    if template.status not in {ServicePlanTemplateStatus.PUBLISHED, ServicePlanTemplateStatus.RETIRED}:
        raise ValidationError("Une nouvelle version se crée depuis un template publié ou retiré.")
    latest = ServicePlanTemplate.objects.select_for_update().filter(service=template.service, key=template.key).order_by("-version").first()
    successor = ServicePlanTemplate.objects.create(service=template.service, key=template.key, version=latest.version + 1, name=(name or template.name).strip(), status=ServicePlanTemplateStatus.DRAFT, created_by=actor)
    mapping = {}
    for source in template.steps.all().order_by("position", "created_at", "id"):
        mapping[source.pk] = ServicePlanTemplateStep.objects.create(template=successor, kind=source.kind, title=source.title, description=source.description, position=source.position, is_required=source.is_required, relative_due_days=source.relative_due_days)
    for source in template.steps.all():
        for dependency in source.dependencies.all():
            ServicePlanTemplateStepDependency.objects.create(step=mapping[source.pk], depends_on=mapping[dependency.depends_on_id])
    return successor


@transaction.atomic
def create_service_journey(*, service, initiated_by, beneficiary=None, external_beneficiary=None, objective="", template=None, expires_at=None, opportunity=None, opportunity_revision=None):
    service = ServiceDetails.objects.select_related("activity").get(pk=service.pk)
    if bool(beneficiary) == bool(external_beneficiary):
        raise ValidationError("Choisissez exactement un bénéficiaire Profile ou externe.")
    if external_beneficiary is not None and not service.allows_external_beneficiary:
        raise ValidationError("Ce Service n’autorise pas de bénéficiaire externe.")
    if template is not None:
        template = (
            ServicePlanTemplate.objects.select_for_update(of=("self",))
            .select_related("service", "service__activity")
            .order_by()
            .get(pk=template.pk)
        )
        if template.service_id != service.pk or template.status != ServicePlanTemplateStatus.PUBLISHED:
            raise ValidationError("La Journey doit utiliser un template publié de ce Service.")
    opportunity, opportunity_revision = resolve_opportunity_selection(
        service=service,
        opportunity=opportunity,
        opportunity_revision=opportunity_revision,
    )
    journey = create_journey_for_holder(initiated_by=initiated_by, beneficiary=beneficiary, external_beneficiary=external_beneficiary, activity=service.activity, workflow=WorkflowKind.SERVICE, occurrence=None, expires_at=expires_at)
    context = ServiceJourneyContext(
        journey=journey,
        service_plan_template=template,
        opportunity=opportunity,
        opportunity_revision=opportunity_revision,
        objective=(objective or "").strip(),
    )
    context.save()
    ensure_requirement_assessments(context=context)
    return journey


def models_q_for_intake(*, service, template):
    from django.db.models import Q
    query = Q(service=service)
    if template is not None:
        query |= Q(template=template)
    return query


def _questions_for_context(context):
    service = context.journey.activity.service_details
    return ServiceIntakeQuestion.objects.filter(models_q_for_intake(service=service, template=context.service_plan_template)).order_by("position", "created_at", "id")


@transaction.atomic
def answer_intake_question(*, journey, question, value, actor):
    if journey.workflow != WorkflowKind.SERVICE:
        raise ValidationError("L’Intake Services exige une Journey SERVICE.")
    if journey.status != JourneyStatus.DRAFT:
        raise ValidationError("L’Intake ne peut être modifié qu’avant la soumission.")
    if not is_beneficiary(actor, journey):
        ensure_case_access(actor, journey, write=True)
    answer, created = ServiceIntakeAnswer.objects.get_or_create(journey=journey, question=question, defaults={"value": value, "answered_by": actor})
    if not created:
        answer.value = value
        answer.answered_by = actor
        answer.save()
    return answer


def _validate_required_intake(context):
    questions = _questions_for_context(context).filter(is_required=True)
    answered_ids = set(ServiceIntakeAnswer.objects.filter(journey=context.journey, question__in=questions).values_list("question_id", flat=True))
    missing = [question.key for question in questions if question.pk not in answered_ids]
    if missing:
        raise ValidationError("Questions Intake obligatoires manquantes: " + ", ".join(missing))


@transaction.atomic
def submit_service_journey(*, journey, actor):
    context = ServiceJourneyContext.objects.select_for_update(of=("self",)).select_related("journey", "journey__activity", "service_plan_template").get(journey=journey)
    if not is_beneficiary(actor, context.journey):
        ensure_case_access(actor, context.journey, write=True)
    _validate_required_intake(context)
    service = context.journey.activity.service_details
    submitted = submit_journey(journey=context.journey, actor=actor, reason="service_intake_submitted")
    if service.intake_policy == IntakePolicy.AUTO_CONFIRM:
        return confirm_journey(journey=submitted, actor=actor, reason="service_auto_confirm")
    create_request(journey=submitted, requester=actor, message="Validation de l’Intake Services")
    submitted.refresh_from_db()
    return submitted


@transaction.atomic
def confirm_service_journey(*, journey, actor):
    context = ServiceJourneyContext.objects.select_for_update(of=("self",)).select_related("journey", "journey__activity").get(journey=journey)
    service = context.journey.activity.service_details
    if service.intake_policy == IntakePolicy.REVIEW_REQUIRED and context.journey.status != JourneyStatus.APPROVED:
        raise ValidationError("Ce Service doit être approuvé avant confirmation.")
    if service.intake_policy == IntakePolicy.AUTO_CONFIRM and context.journey.status != JourneyStatus.SUBMITTED:
        if context.journey.status == JourneyStatus.CONFIRMED:
            return context.journey
        raise ValidationError("Ce Service auto-confirmé doit être soumis avant confirmation.")
    if not is_beneficiary(actor, context.journey):
        ensure_case_access(actor, context.journey, write=True)
    return confirm_journey(journey=context.journey, actor=actor, reason="service_confirmed")


@transaction.atomic
def materialize_service_plan(*, context, actor):
    context = ServiceJourneyContext.objects.select_for_update(of=("self",)).select_related("journey", "journey__activity", "service_plan_template", "service_plan_template__service").order_by().get(pk=context.pk)
    ensure_case_access(actor, context.journey, write=True)
    if context.plan_materialized_at is not None:
        return list(context.materialized_steps.select_related("journey_step", "template_step"))
    template = context.service_plan_template
    if template is None or template.status != ServicePlanTemplateStatus.PUBLISHED:
        raise ValidationError("Un template Services publié est requis avant matérialisation.")
    if template.service.activity_id != context.journey.activity_id:
        raise ValidationError("Le template ne correspond pas à l’Activity de la Journey.")
    template_steps = list(template.steps.all().order_by("position", "created_at", "id"))
    if not template_steps:
        raise ValidationError("Le template Services ne contient aucune étape.")
    mapping = {}
    now = timezone.now()
    for template_step in template_steps:
        due_at = now + timedelta(days=template_step.relative_due_days) if template_step.relative_due_days is not None else None
        journey_step = create_step(journey=context.journey, title=template_step.title, kind=template_step.kind, description=template_step.description, position=template_step.position, is_required=template_step.is_required, due_at=due_at, origin=JourneyStepOrigin.TEMPLATE, created_by=actor)
        mapping[template_step.pk] = journey_step
        ServicePlanMaterialization.objects.create(context=context, template_step=template_step, journey_step=journey_step)
    for dependency in ServicePlanTemplateStepDependency.objects.filter(step__template=template).select_related("step", "depends_on"):
        add_step_dependency(step=mapping[dependency.step_id], depends_on=mapping[dependency.depends_on_id], actor=actor)
    for journey_step in mapping.values():
        if journey_step.status == JourneyStepStatus.PENDING and not journey_step.dependencies.exists():
            mark_ready(step=journey_step, actor=actor, reason="service_plan_materialized")
    context.plan_materialized_at = now
    context.save(update_fields=["plan_materialized_at", "updated_at"])
    return list(context.materialized_steps.select_related("journey_step", "template_step"))


@transaction.atomic
def start_service_journey(*, journey, actor):
    context = ServiceJourneyContext.objects.select_for_update(of=("self",)).select_related("journey", "journey__activity", "service_plan_template", "opportunity", "opportunity_revision").get(journey=journey)
    ensure_case_access(actor, context.journey, write=True)
    if context.journey.status != JourneyStatus.CONFIRMED:
        raise ValidationError("La Journey Services doit être confirmée avant démarrage.")
    service = context.journey.activity.service_details
    if service.opportunity_policy == OpportunityPolicy.REQUIRED and (not context.opportunity_id or not context.opportunity_revision_id):
        raise ValidationError("Ce Service exige une Opportunity et une révision pinnée avant démarrage.")
    ensure_requirement_assessments(context=context)
    materialize_service_plan(context=context, actor=actor)
    return start_journey(journey=context.journey, actor=actor, reason="service_started")


def validate_service_completion(journey):
    if journey.workflow != WorkflowKind.SERVICE or journey.status != JourneyStatus.IN_PROGRESS:
        raise ValidationError("La completion policy s’applique à une Journey Services en cours.")
    try:
        context = journey.service_context
    except ServiceJourneyContext.DoesNotExist as exc:
        raise ValidationError("La Journey Services n’a pas de contexte.") from exc
    service = journey.activity.service_details
    if service.completion_policy != CompletionPolicy.REQUIRED_STEPS:
        raise ValidationError("Completion policy Services T31 inconnue.")
    if context.plan_materialized_at is None:
        raise ValidationError("Le plan Services n’a pas été matérialisé.")
    validate_requirement_completion(context)
    required = journey.steps.filter(is_required=True)
    if not required.exists():
        raise ValidationError("Le plan Services matérialisé ne contient aucune étape obligatoire.")
    for step in required:
        if step.status == JourneyStepStatus.COMPLETED:
            pass
        elif step.status == JourneyStepStatus.SKIPPED and step.status_changed_by_id and step.status_reason:
            pass
        else:
            raise ValidationError(f"Étape obligatoire non satisfaite: {step.title}")
        if step.kind == JourneyStepKind.REVIEW and not step.artifacts.filter(reviews__status=JourneyArtifactReviewStatus.APPROVED).exists():
            raise ValidationError(f"Revue obligatoire non approuvée: {step.title}")
    if journey.blockers.filter(status=JourneyBlockerStatus.ACTIVE, severity=JourneyBlockerSeverity.CRITICAL).exists():
        raise ValidationError("Un blocker critique actif empêche la clôture.")
    if journey.blockers.filter(status=JourneyBlockerStatus.ACTIVE, step__is_required=True).exists():
        raise ValidationError("Un blocker actif empêche une étape obligatoire.")
    return True


@transaction.atomic
def fulfill_service_journey(*, journey, actor):
    journey.refresh_from_db()
    ensure_case_access(actor, journey, write=True)
    validate_service_completion(journey)
    return _fulfill_service_journey(journey=journey, actor=actor)
