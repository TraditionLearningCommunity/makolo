from __future__ import annotations

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from domain_events.contracts import DomainEventType
from domain_events.services import emit_domain_event
from journeys.collaboration_services import ensure_case_access, is_beneficiary
from opportunities.models import Opportunity, OpportunityPublicationStatus, OpportunityRevision
from opportunities.services import canonical_opportunity

from .models import (
    OpportunityPolicy,
    ServiceJourneyContext,
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


def resolve_opportunity_selection(*, service, opportunity=None, opportunity_revision=None):
    if opportunity_revision is not None and opportunity is None:
        opportunity = opportunity_revision.opportunity
    if service.opportunity_policy == OpportunityPolicy.NONE:
        if opportunity is not None or opportunity_revision is not None:
            raise ValidationError("Ce Service est configuré sans Opportunity.")
        return None, None
    if opportunity is None:
        if service.opportunity_policy == OpportunityPolicy.REQUIRED:
            raise ValidationError("Ce Service exige une Opportunity publiée.")
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
            raise ValidationError("Une nouvelle Journey doit démarrer sur la révision Opportunity courante.")
    if opportunity_revision.published_at is None:
        raise ValidationError("La Journey doit pinner une OpportunityRevision publiée.")
    return opportunity, opportunity_revision


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
def link_requirement_step(*, context, requirement, journey_step, actor):
    context = ServiceJourneyContext.objects.select_related("journey", "journey__activity").get(pk=context.pk)
    ensure_case_access(actor, context.journey, write=True)
    if requirement.revision_id != context.opportunity_revision_id:
        raise ValidationError("Le Requirement doit appartenir à la révision actuellement pinnée.")
    if journey_step.journey_id != context.journey_id:
        raise ValidationError("La JourneyStep appartient à un autre dossier.")
    link, _ = ServiceRequirementStepLink.objects.get_or_create(
        context=context,
        requirement=requirement,
        journey_step=journey_step,
        defaults={"created_by": actor},
    )
    return link


def requirement_progress(context):
    if context.opportunity_revision_id is None:
        return {
            "total": 0,
            "settled": 0,
            "mandatory_total": 0,
            "mandatory_satisfied": 0,
            "complete": True,
        }
    assessments = list(
        ServiceRequirementAssessment.objects.filter(
            context=context,
            requirement__revision_id=context.opportunity_revision_id,
        ).select_related("requirement")
    )
    total = len(assessments)
    settled = sum(1 for item in assessments if item.status in SATISFIED_REQUIREMENT_STATUSES)
    mandatory = [item for item in assessments if item.requirement.is_mandatory]
    mandatory_satisfied = sum(1 for item in mandatory if item.status in SATISFIED_REQUIREMENT_STATUSES)
    return {
        "total": total,
        "settled": settled,
        "mandatory_total": len(mandatory),
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
    context._allow_opportunity_adoption = True
    context.save(update_fields=["opportunity_revision", "updated_at"])
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
