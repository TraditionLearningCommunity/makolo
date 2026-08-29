from __future__ import annotations

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from domain_events.contracts import DomainEventType
from domain_events.services import emit_domain_event
from journeys.collaboration_models import JourneyStepKind, JourneyStepOrigin
from journeys.collaboration_services import create_step, ensure_case_access, is_beneficiary, mark_ready
from journeys.models import JourneyStatus
from opportunities.models import (
    Opportunity,
    OpportunityPublicationStatus,
    OpportunityRequirementKind,
    OpportunityRevision,
)
from opportunities.services import canonical_opportunity

from .models import (
    OpportunityPolicy,
    ServiceJourneyContext,
    ServiceOpportunityRevisionAdoption,
    ServiceRequirementAssessment,
    ServiceRequirementAssessmentStatus,
    ServiceRequirementEvidence,
    ServiceRequirementEvidenceStatus,
    ServiceRequirementStepLink,
)


SATISFIED_REQUIREMENT_STATUSES = {
    ServiceRequirementAssessmentStatus.SATISFIED,
    ServiceRequirementAssessmentStatus.NOT_APPLICABLE,
}
CURRENT_PROGRESS_STATUSES = tuple(ServiceRequirementAssessmentStatus.values)


def resolve_opportunity_selection(*, service, opportunity=None, opportunity_revision=None):
    if opportunity_revision is not None and opportunity is None:
        opportunity = opportunity_revision.opportunity
    if service.opportunity_policy == OpportunityPolicy.NONE:
        if opportunity is not None or opportunity_revision is not None:
            raise ValidationError("Ce Service est configuré sans Opportunity.")
        return None, None
    if opportunity is None:
        return None, None

    opportunity = Opportunity.objects.select_related("merged_into").get(pk=opportunity.pk)
    opportunity = canonical_opportunity(opportunity)
    if opportunity.publication_status != OpportunityPublicationStatus.PUBLISHED:
        raise ValidationError("Une nouvelle Journey Services exige une Opportunity actuellement publiée.")
    if not opportunity.current_revision_id:
        raise ValidationError("L’Opportunity publiée ne possède pas de révision courante.")

    if opportunity_revision is None:
        opportunity_revision = OpportunityRevision.objects.get(pk=opportunity.current_revision_id)
    else:
        opportunity_revision = OpportunityRevision.objects.get(pk=opportunity_revision.pk)
        if opportunity_revision.opportunity_id != opportunity.pk:
            raise ValidationError("La révision sélectionnée appartient à une autre Opportunity.")
        if opportunity_revision.pk != opportunity.current_revision_id:
            raise ValidationError("Une nouvelle liaison doit démarrer sur la révision Opportunity courante.")
    if opportunity_revision.published_at is None:
        raise ValidationError("La Journey doit pinner une OpportunityRevision publiée.")
    return opportunity, opportunity_revision


def has_newer_opportunity_revision(context) -> bool:
    if not context.opportunity_id or not context.opportunity_revision_id:
        return False
    opportunity = Opportunity.objects.select_related("current_revision").filter(pk=context.opportunity_id).first()
    if not opportunity or not opportunity.current_revision_id or opportunity.current_revision.published_at is None:
        return False
    if opportunity.current_revision.opportunity_id != context.opportunity_id:
        return False
    return opportunity.current_revision.version > context.opportunity_revision.version


@transaction.atomic
def attach_opportunity_to_service_journey(*, context, opportunity, actor, opportunity_revision=None):
    context = (
        ServiceJourneyContext.objects.select_for_update(of=("self",))
        .select_related("journey", "journey__activity", "journey__activity__service_details")
        .order_by()
        .get(pk=context.pk)
    )
    if not is_beneficiary(actor, context.journey):
        ensure_case_access(actor, context.journey, write=True)
    if context.opportunity_id or context.opportunity_revision_id:
        raise ValidationError("Ce dossier possède déjà une Opportunity ; utilisez l’adoption pour une nouvelle révision.")
    if context.journey.status in {
        JourneyStatus.IN_PROGRESS,
        JourneyStatus.FULFILLED,
        JourneyStatus.CANCELLED,
        JourneyStatus.EXPIRED,
    }:
        raise ValidationError("L’Opportunity doit être attachée avant le démarrage opérationnel du dossier.")
    service = context.journey.activity.service_details
    opportunity, opportunity_revision = resolve_opportunity_selection(
        service=service,
        opportunity=opportunity,
        opportunity_revision=opportunity_revision,
    )
    if opportunity is None:
        raise ValidationError("Une Opportunity publiée est requise pour cette liaison.")
    context.opportunity = opportunity
    context.opportunity_revision = opportunity_revision
    context._allow_opportunity_change = True
    context.save(update_fields=["opportunity", "opportunity_revision", "updated_at"])
    ensure_requirement_assessments(context=context)
    return context


@transaction.atomic
def ensure_requirement_assessments(*, context):
    context = (
        ServiceJourneyContext.objects.select_for_update(of=("self",))
        .select_related("opportunity_revision")
        .order_by()
        .get(pk=context.pk)
    )
    if context.opportunity_revision_id is None:
        return []
    requirements = list(context.opportunity_revision.requirements.all().order_by("position", "created_at", "id"))
    for requirement in requirements:
        ServiceRequirementAssessment.objects.get_or_create(context=context, requirement=requirement)
    return list(
        ServiceRequirementAssessment.objects.filter(
            context=context,
            requirement__revision_id=context.opportunity_revision_id,
        ).select_related("requirement").order_by("requirement__position", "created_at", "id")
    )


@transaction.atomic
def assess_requirement(*, assessment, actor, status, note=""):
    assessment = (
        ServiceRequirementAssessment.objects.select_for_update(of=("self",))
        .select_related("context", "context__journey", "context__journey__activity", "requirement")
        .order_by()
        .get(pk=assessment.pk)
    )
    ensure_case_access(actor, assessment.context.journey, write=True)
    if assessment.requirement.revision_id != assessment.context.opportunity_revision_id:
        raise ValidationError("Cette Assessment appartient à une ancienne révision pinnée et reste historique.")
    if status not in ServiceRequirementAssessmentStatus.values:
        raise ValidationError("Statut Requirement Assessment invalide.")
    assessment.status = status
    assessment.note = note or ""
    if status == ServiceRequirementAssessmentStatus.UNASSESSED:
        assessment.assessed_by = None
        assessment.assessed_at = None
    else:
        assessment.assessed_by = actor
        assessment.assessed_at = timezone.now()
    assessment._allow_assessment_transition = True
    assessment.save()
    return assessment


@transaction.atomic
def submit_requirement_evidence(*, assessment, artifact, actor):
    assessment = ServiceRequirementAssessment.objects.select_related(
        "context", "context__journey", "context__journey__activity", "requirement"
    ).get(pk=assessment.pk)
    if assessment.requirement.revision_id != assessment.context.opportunity_revision_id:
        raise ValidationError("Une preuve ne peut être ajoutée qu’aux Requirements de la révision actuellement pinnée.")
    if not is_beneficiary(actor, assessment.context.journey):
        ensure_case_access(actor, assessment.context.journey, write=True)
    if artifact.journey_id != assessment.context.journey_id:
        raise PermissionDenied("Cette pièce n’appartient pas au dossier Services.")
    evidence, _ = ServiceRequirementEvidence.objects.get_or_create(
        assessment=assessment,
        artifact=artifact,
        defaults={"submitted_by": actor},
    )
    return evidence


@transaction.atomic
def review_requirement_evidence(*, evidence, actor, decision, review_note=""):
    evidence = (
        ServiceRequirementEvidence.objects.select_for_update(of=("self",))
        .select_related("assessment", "assessment__context", "assessment__context__journey", "assessment__context__journey__activity")
        .order_by()
        .get(pk=evidence.pk)
    )
    ensure_case_access(actor, evidence.assessment.context.journey, write=True)
    if decision not in {ServiceRequirementEvidenceStatus.ACCEPTED, ServiceRequirementEvidenceStatus.REJECTED}:
        raise ValidationError("La revue d’une preuve doit être accepted ou rejected.")
    evidence.status = decision
    evidence.reviewed_by = actor
    evidence.reviewed_at = timezone.now()
    evidence.review_note = review_note or ""
    evidence._allow_evidence_transition = True
    evidence.save()
    return evidence


@transaction.atomic
def link_requirement_step(*, assessment, journey_step, actor):
    assessment = ServiceRequirementAssessment.objects.select_related(
        "context", "context__journey", "context__journey__activity", "requirement"
    ).get(pk=assessment.pk)
    ensure_case_access(actor, assessment.context.journey, write=True)
    if assessment.requirement.revision_id != assessment.context.opportunity_revision_id:
        raise ValidationError("L’Assessment doit appartenir à la révision actuellement pinnée.")
    if journey_step.journey_id != assessment.context.journey_id:
        raise ValidationError("La JourneyStep appartient à un autre dossier.")
    link, _ = ServiceRequirementStepLink.objects.get_or_create(
        assessment=assessment,
        journey_step=journey_step,
        defaults={"created_by": actor},
    )
    return link


def _default_step_kind(requirement_kind):
    if requirement_kind == OpportunityRequirementKind.DOCUMENT:
        return JourneyStepKind.DOCUMENT
    if requirement_kind == OpportunityRequirementKind.FINANCIAL:
        return JourneyStepKind.PAYMENT
    return JourneyStepKind.ACTION


@transaction.atomic
def create_requirement_step(
    *,
    assessment,
    actor,
    title=None,
    description=None,
    kind=None,
    position=None,
    allow_additional=False,
):
    assessment = (
        ServiceRequirementAssessment.objects.select_for_update(of=("self",))
        .select_related("context", "context__journey", "context__journey__activity", "requirement")
        .order_by()
        .get(pk=assessment.pk)
    )
    ensure_case_access(actor, assessment.context.journey, write=True)
    if assessment.requirement.revision_id != assessment.context.opportunity_revision_id:
        raise ValidationError("Une ancienne Assessment ne peut plus générer d’action courante.")
    existing = assessment.step_links.select_related("journey_step").order_by("created_at", "id").first()
    if existing is not None and not allow_additional:
        return existing
    if assessment.status in SATISFIED_REQUIREMENT_STATUSES:
        if existing is not None:
            return existing
        raise ValidationError("Un Requirement déjà satisfait ne génère pas de nouvelle action.")
    if position is None:
        position = (assessment.context.journey.steps.aggregate(value=Max("position"))["value"] or 0) + 10
    step = create_step(
        journey=assessment.context.journey,
        title=(title or assessment.requirement.title).strip(),
        kind=kind or _default_step_kind(assessment.requirement.kind),
        description=description if description is not None else assessment.requirement.description,
        position=position,
        is_required=assessment.requirement.is_mandatory,
        origin=JourneyStepOrigin.MANUAL,
        created_by=actor,
    )
    if not step.dependencies.exists():
        mark_ready(step=step, actor=actor, reason="requirement_action_created")
    return ServiceRequirementStepLink.objects.create(
        assessment=assessment,
        journey_step=step,
        created_by=actor,
    )


def requirement_progress(context):
    counts = {status: 0 for status in CURRENT_PROGRESS_STATUSES}
    if context.opportunity_revision_id is None:
        return {
            "total": 0,
            "mandatory_total": 0,
            **counts,
            "mandatory_satisfied": 0,
            "complete": True,
        }
    assessments = list(
        ServiceRequirementAssessment.objects.filter(
            context=context,
            requirement__revision_id=context.opportunity_revision_id,
        ).select_related("requirement")
    )
    for item in assessments:
        counts[item.status] += 1
    mandatory = [item for item in assessments if item.requirement.is_mandatory]
    mandatory_satisfied = sum(1 for item in mandatory if item.status in SATISFIED_REQUIREMENT_STATUSES)
    return {
        "total": len(assessments),
        "mandatory_total": len(mandatory),
        **counts,
        "mandatory_satisfied": mandatory_satisfied,
        "complete": mandatory_satisfied == len(mandatory),
    }


def validate_requirement_completion(context):
    if context.opportunity_revision_id is None:
        return True
    expected = context.opportunity_revision.requirements.filter(is_mandatory=True).count()
    assessments = ServiceRequirementAssessment.objects.filter(
        context=context,
        requirement__revision_id=context.opportunity_revision_id,
        requirement__is_mandatory=True,
    )
    if assessments.count() != expected:
        raise ValidationError("Les Requirements obligatoires de la révision pinnée n’ont pas tous été évalués.")
    blockers = assessments.exclude(status__in=SATISFIED_REQUIREMENT_STATUSES).select_related("requirement")
    first = blockers.first()
    if first is not None:
        raise ValidationError(f"Requirement obligatoire non satisfait: {first.requirement.title}")
    return True


@transaction.atomic
def adopt_opportunity_revision(*, context, revision, actor):
    context = (
        ServiceJourneyContext.objects.select_for_update(of=("self",))
        .select_related("journey", "journey__activity", "opportunity", "opportunity_revision")
        .order_by()
        .get(pk=context.pk)
    )
    # A concurrent SELECT may have established its snapshot before waiting for
    # the row lock. Refresh the pinned FK after the lock so a later transaction
    # never evaluates its candidate against a stale related-object snapshot.
    context.refresh_from_db(fields=["opportunity", "opportunity_revision"])
    ensure_case_access(actor, context.journey, write=True)
    if context.opportunity_id is None or context.opportunity_revision_id is None:
        raise ValidationError("Ce dossier Services n’est pas lié à une Opportunity.")
    revision = OpportunityRevision.objects.select_related("opportunity").get(pk=revision.pk)
    if revision.opportunity_id != context.opportunity_id:
        raise ValidationError("La nouvelle révision appartient à une autre Opportunity.")
    if revision.published_at is None:
        raise ValidationError("Seule une OpportunityRevision publiée peut être adoptée.")
    previous = context.opportunity_revision
    if revision.pk == previous.pk:
        return context
    if revision.version <= previous.version:
        raise ValidationError("L’adoption doit avancer vers une version Opportunity plus récente.")
    context.opportunity_revision = revision
    context._allow_opportunity_change = True
    context.save(update_fields=["opportunity_revision", "updated_at"])
    ServiceOpportunityRevisionAdoption.objects.get_or_create(
        context=context,
        revision=revision,
        defaults={"previous_revision": previous, "adopted_by": actor},
    )
    ensure_requirement_assessments(context=context)
    emit_domain_event(
        event_type=DomainEventType.SERVICE_OPPORTUNITY_REVISION_ADOPTED,
        source_type="service_journey_context",
        source_id=context.pk,
        idempotency_key=f"service_journey_context:{context.pk}:adopt:{revision.pk}"[:255],
        activity_id=context.journey.activity_id,
        space_id=getattr(context.journey.activity, "space_id", None),
        payload={
            "journey_id": str(context.journey_id),
            "opportunity_id": str(context.opportunity_id),
            "previous_revision_id": str(previous.pk),
            "revision_id": str(revision.pk),
            "version": revision.version,
        },
    )
    return context
