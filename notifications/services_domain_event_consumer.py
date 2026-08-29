from __future__ import annotations

from django.db.models import Q
from django.urls import reverse

from authorization.constants import PermissionCode
from authorization.models import AuthorityScope, Mandate, MandateStatus
from authorization.services import can
from domain_events.contracts import DomainEventType
from domain_events.registry import register_consumer
from journeys.collaboration_models import (
    JourneyArtifactReview,
    JourneyArtifactReviewStatus,
    JourneyArtifactSensitivity,
    JourneyAssignment,
    JourneyAssignmentStatus,
    JourneyStep,
    JourneyStepStatus,
)
from journeys.models import Journey, JourneyStatus, WorkflowKind
from journeys.service_authorization import (
    CASE_SCOPE_VIEW_ALL,
    CASE_SCOPE_VIEW_ASSIGNED,
    service_case_scope,
)
from opportunities.models import Opportunity, OpportunityRevision, OpportunitySave
from payments.models import PaymentEvidence, PaymentEvidenceStatus, PaymentObligation, PaymentObligationStatus
from services.models import ServiceJourneyContext, ServiceSubmission

from .models import NotificationCategory, NotificationKind
from .services import create_notification


CONSUMER_NAME = "notifications.services_opportunities"
EVENT_TYPES = {
    DomainEventType.JOURNEY_IN_PROGRESS,
    DomainEventType.JOURNEY_STEP_READY,
    DomainEventType.JOURNEY_STEP_BLOCKED,
    DomainEventType.JOURNEY_ASSIGNMENT_CREATED,
    DomainEventType.JOURNEY_ASSIGNMENT_ENDED,
    DomainEventType.JOURNEY_ARTIFACT_REVIEW_REQUESTED,
    DomainEventType.JOURNEY_ARTIFACT_REVIEW_COMPLETED,
    DomainEventType.PAYMENT_OBLIGATION_CREATED,
    DomainEventType.PAYMENT_EVIDENCE_SUBMITTED,
    DomainEventType.PAYMENT_EVIDENCE_VERIFIED,
    DomainEventType.PAYMENT_EVIDENCE_REJECTED,
    DomainEventType.SERVICE_SUBMISSION_SUBMITTED,
    DomainEventType.SERVICE_SUBMISSION_ACKNOWLEDGED,
    DomainEventType.SERVICE_SUBMISSION_FAILED,
    DomainEventType.SERVICE_SUBMISSION_WITHDRAWN,
    DomainEventType.SERVICE_OUTCOME_CHANGED,
    DomainEventType.OPPORTUNITY_REVISION_PUBLISHED,
    DomainEventType.OPPORTUNITY_WITHDRAWN,
    DomainEventType.OPPORTUNITY_SOURCE_CHANGED,
}
ACTIVE_CASE_STATUSES = {
    JourneyStatus.DRAFT,
    JourneyStatus.SUBMITTED,
    JourneyStatus.PENDING_APPROVAL,
    JourneyStatus.APPROVED,
    JourneyStatus.PENDING_PAYMENT,
    JourneyStatus.CONFIRMED,
    JourneyStatus.IN_PROGRESS,
}
OPERATOR_SCOPES = {CASE_SCOPE_VIEW_ALL, CASE_SCOPE_VIEW_ASSIGNED}


def _dedup(event, recipient, template_key):
    return f"domain:{event.pk}:{recipient.pk}:{template_key}"[:255]


def _journey_action(journey):
    return reverse("core:participant-journey-detail", kwargs={"pk": journey.pk})


def _notify(
    *,
    event,
    recipient,
    category,
    template_key,
    title,
    message,
    journey=None,
    activity=None,
    metadata=None,
    action_url="",
):
    return create_notification(
        recipient=recipient,
        kind=NotificationKind.SYSTEM,
        category=category,
        title=title,
        message=message,
        action_url=action_url,
        dedup_key=_dedup(event, recipient, template_key),
        metadata=metadata or {},
        domain_event=event,
        activity=activity,
        journey=journey,
        template_key=template_key,
    )


def _service_journey(event):
    journey_id = (event.payload or {}).get("journey_id")
    if not journey_id:
        return None
    return (
        Journey.objects.select_related("beneficiary", "activity")
        .filter(pk=journey_id, workflow=WorkflowKind.SERVICE)
        .first()
    )


def _activity_operator_candidates(activity):
    return (
        Mandate.objects.filter(
            scope_type=AuthorityScope.ACTIVITY,
            activity=activity,
            status=MandateStatus.ACTIVE,
            profile__is_active=True,
        )
        .select_related("profile", "role")
        .order_by("profile_id")
    )


def _profiles_with_case_permission(journey, permission_code):
    seen = set()
    for mandate in _activity_operator_candidates(journey.activity):
        profile = mandate.profile
        if profile.pk in seen:
            continue
        seen.add(profile.pk)
        if service_case_scope(profile, journey) not in OPERATOR_SCOPES:
            continue
        if can(profile, permission_code, activity=journey.activity):
            yield profile


def _notify_journey_started(event):
    journey = _service_journey(event)
    if not journey or not journey.beneficiary_id:
        return
    _notify(
        event=event,
        recipient=journey.beneficiary,
        category=NotificationCategory.SERVICE,
        template_key="service.journey.in_progress",
        title="Votre accompagnement a commencé",
        message="Votre démarche est maintenant en cours d’accompagnement.",
        journey=journey,
        activity=journey.activity,
        metadata={"journey_id": str(journey.pk)},
        action_url=_journey_action(journey),
    )


def _notify_step(event):
    step_id = (event.payload or {}).get("step_id")
    step = (
        JourneyStep.objects.select_related("journey__beneficiary", "journey__activity")
        .filter(pk=step_id, journey__workflow=WorkflowKind.SERVICE)
        .first()
    )
    if not step or not step.journey.beneficiary_id:
        return
    if event.event_type == DomainEventType.JOURNEY_STEP_READY:
        if step.status != JourneyStepStatus.READY:
            return
        title = "Une étape est prête"
        message = "Une étape de votre démarche peut maintenant être poursuivie."
        template_key = "service.step.ready"
    else:
        if step.status != JourneyStepStatus.BLOCKED:
            return
        title = "Votre démarche nécessite votre attention"
        message = "Une étape de votre démarche nécessite votre attention."
        template_key = "service.step.blocked"
    _notify(
        event=event,
        recipient=step.journey.beneficiary,
        category=NotificationCategory.SERVICE,
        template_key=template_key,
        title=title,
        message=message,
        journey=step.journey,
        activity=step.journey.activity,
        metadata={"journey_id": str(step.journey_id), "step_id": str(step.pk)},
        action_url=_journey_action(step.journey),
    )


def _notify_assignment(event):
    assignment_id = (event.payload or {}).get("assignment_id")
    assignment = (
        JourneyAssignment.objects.select_related("profile", "journey__activity")
        .filter(pk=assignment_id, journey__workflow=WorkflowKind.SERVICE)
        .first()
    )
    if not assignment or not assignment.profile.is_active:
        return
    if event.event_type == DomainEventType.JOURNEY_ASSIGNMENT_CREATED:
        if assignment.status != JourneyAssignmentStatus.ACTIVE:
            return
        if service_case_scope(assignment.profile, assignment.journey) not in OPERATOR_SCOPES:
            return
        title = "Une responsabilité vous a été attribuée"
        message = "Un dossier Services vous a été affecté dans le cadre de vos autorisations actuelles."
        template_key = "service.assignment.created"
    else:
        if assignment.status == JourneyAssignmentStatus.ACTIVE:
            return
        title = "Votre responsabilité sur un dossier est terminée"
        message = "Votre affectation opérationnelle sur un dossier Services a pris fin."
        template_key = "service.assignment.ended"
    _notify(
        event=event,
        recipient=assignment.profile,
        category=NotificationCategory.SERVICE,
        template_key=template_key,
        title=title,
        message=message,
        journey=assignment.journey,
        activity=assignment.journey.activity,
        metadata={"journey_id": str(assignment.journey_id), "assignment_id": str(assignment.pk)},
    )


def _review_is_authorized(review):
    reviewer = review.reviewer
    journey = review.artifact.journey
    if not reviewer.is_active:
        return False
    if service_case_scope(reviewer, journey) not in OPERATOR_SCOPES:
        return False
    if not JourneyAssignment.objects.filter(
        journey=journey,
        profile=reviewer,
        status=JourneyAssignmentStatus.ACTIVE,
    ).exists():
        return False
    if not can(reviewer, PermissionCode.ACTIVITY_SERVICES_REVIEWS_MANAGE, activity=journey.activity):
        return False
    if not can(reviewer, PermissionCode.ACTIVITY_SERVICES_ARTIFACTS_VIEW, activity=journey.activity):
        return False
    if review.artifact.sensitivity == JourneyArtifactSensitivity.RESTRICTED and not can(
        reviewer,
        PermissionCode.ACTIVITY_SERVICES_ARTIFACTS_RESTRICTED_VIEW,
        activity=journey.activity,
    ):
        return False
    return True


def _notify_review(event):
    review_id = (event.payload or {}).get("review_id")
    review = (
        JourneyArtifactReview.objects.select_related(
            "reviewer",
            "artifact__journey__beneficiary",
            "artifact__journey__activity",
        )
        .filter(pk=review_id, artifact__journey__workflow=WorkflowKind.SERVICE)
        .first()
    )
    if not review:
        return
    journey = review.artifact.journey
    if event.event_type == DomainEventType.JOURNEY_ARTIFACT_REVIEW_REQUESTED:
        if review.status not in {JourneyArtifactReviewStatus.REQUESTED, JourneyArtifactReviewStatus.IN_PROGRESS}:
            return
        if not _review_is_authorized(review):
            return
        _notify(
            event=event,
            recipient=review.reviewer,
            category=NotificationCategory.SERVICE,
            template_key="service.artifact.review_requested",
            title="Un document est à revoir",
            message="Un document d’un dossier qui vous est affecté nécessite votre revue.",
            journey=journey,
            activity=journey.activity,
            metadata={"journey_id": str(journey.pk), "review_id": str(review.pk)},
        )
        return
    if not journey.beneficiary_id:
        return
    if review.status == JourneyArtifactReviewStatus.APPROVED:
        message = "Votre document a été revu et validé."
    elif review.status == JourneyArtifactReviewStatus.CHANGES_REQUESTED:
        message = "Votre document a été revu. Des modifications sont demandées."
    else:
        return
    _notify(
        event=event,
        recipient=journey.beneficiary,
        category=NotificationCategory.SERVICE,
        template_key="service.artifact.review_completed",
        title="Votre document a été revu",
        message=message,
        journey=journey,
        activity=journey.activity,
        metadata={"journey_id": str(journey.pk), "review_id": str(review.pk)},
        action_url=_journey_action(journey),
    )


def _notify_payment_obligation(event):
    obligation_id = (event.payload or {}).get("obligation_id")
    obligation = (
        PaymentObligation.objects.select_related("journey__beneficiary", "journey__activity")
        .filter(pk=obligation_id, journey__workflow=WorkflowKind.SERVICE)
        .first()
    )
    if not obligation or not obligation.journey.beneficiary_id or obligation.status != PaymentObligationStatus.PENDING:
        return
    due = f" Échéance : {obligation.due_at.date().isoformat()}." if obligation.due_at else ""
    _notify(
        event=event,
        recipient=obligation.journey.beneficiary,
        category=NotificationCategory.SERVICE,
        template_key="service.payment_obligation.created",
        title="Une action de paiement est requise",
        message=f"Une obligation de {obligation.amount} {obligation.currency} nécessite votre action.{due}",
        journey=obligation.journey,
        activity=obligation.journey.activity,
        metadata={"journey_id": str(obligation.journey_id), "obligation_id": str(obligation.pk)},
        action_url=_journey_action(obligation.journey),
    )


def _notify_payment_evidence(event):
    evidence_id = (event.payload or {}).get("evidence_id")
    evidence = (
        PaymentEvidence.objects.select_related(
            "submitted_by",
            "obligation__journey__beneficiary",
            "obligation__journey__activity",
        )
        .filter(pk=evidence_id, obligation__journey__workflow=WorkflowKind.SERVICE)
        .first()
    )
    if not evidence:
        return
    journey = evidence.obligation.journey
    if event.event_type == DomainEventType.PAYMENT_EVIDENCE_SUBMITTED:
        if evidence.status != PaymentEvidenceStatus.SUBMITTED:
            return
        for recipient in _profiles_with_case_permission(
            journey,
            PermissionCode.ACTIVITY_SERVICES_PAYMENT_EVIDENCE_VERIFY,
        ):
            _notify(
                event=event,
                recipient=recipient,
                category=NotificationCategory.SERVICE,
                template_key="service.payment_evidence.submitted",
                title="Une preuve de paiement est à vérifier",
                message="Une preuve de paiement a été soumise et nécessite une vérification.",
                journey=journey,
                activity=journey.activity,
                metadata={"journey_id": str(journey.pk), "evidence_id": str(evidence.pk)},
            )
        return
    recipient = evidence.submitted_by or journey.beneficiary
    if recipient is None:
        return
    if evidence.status == PaymentEvidenceStatus.VERIFIED:
        title = "Preuve de paiement validée"
        message = "Votre preuve de paiement a été vérifiée."
        template_key = "service.payment_evidence.verified"
    elif evidence.status == PaymentEvidenceStatus.REJECTED:
        title = "Preuve de paiement à corriger"
        message = "Votre preuve de paiement n’a pas été validée. Consultez votre démarche pour la suite."
        template_key = "service.payment_evidence.rejected"
    else:
        return
    _notify(
        event=event,
        recipient=recipient,
        category=NotificationCategory.SERVICE,
        template_key=template_key,
        title=title,
        message=message,
        journey=journey,
        activity=journey.activity,
        metadata={"journey_id": str(journey.pk), "evidence_id": str(evidence.pk)},
        action_url=_journey_action(journey) if recipient.pk == journey.beneficiary_id else "",
    )


def _notify_submission(event):
    submission = (
        ServiceSubmission.objects.select_related("context__journey__beneficiary", "context__journey__activity")
        .filter(pk=event.source_id, context__journey__workflow=WorkflowKind.SERVICE)
        .first()
    )
    if not submission or not submission.context.journey.beneficiary_id:
        return
    copy = {
        DomainEventType.SERVICE_SUBMISSION_SUBMITTED: ("Dossier transmis", "Votre dossier a été indiqué comme transmis."),
        DomainEventType.SERVICE_SUBMISSION_ACKNOWLEDGED: ("Réception confirmée", "La réception de votre dossier a été enregistrée."),
        DomainEventType.SERVICE_SUBMISSION_FAILED: ("Transmission non aboutie", "La transmission de votre dossier n’a pas abouti et nécessite votre attention."),
        DomainEventType.SERVICE_SUBMISSION_WITHDRAWN: ("Soumission retirée", "Votre soumission a été indiquée comme retirée."),
    }
    title, message = copy[event.event_type]
    _notify(
        event=event,
        recipient=submission.context.journey.beneficiary,
        category=NotificationCategory.SERVICE,
        template_key=event.event_type,
        title=title,
        message=message,
        journey=submission.context.journey,
        activity=submission.context.journey.activity,
        metadata={"journey_id": str(submission.context.journey_id), "submission_id": str(submission.pk)},
        action_url=_journey_action(submission.context.journey),
    )


def _notify_outcome(event):
    context_id = (event.payload or {}).get("context_id")
    context = (
        ServiceJourneyContext.objects.select_related("journey__beneficiary", "journey__activity")
        .filter(pk=context_id)
        .first()
    )
    if not context or not context.journey.beneficiary_id or not (event.payload or {}).get("projection_changed", True):
        return
    outcome = context.current_outcome
    copy = {
        "under_review": ("Votre dossier est en revue", "Le dossier externe est indiqué comme étant en revue."),
        "action_required": ("Une action externe est requise", "Une action est demandée concernant votre démarche externe."),
        "interview": ("Étape d’entretien signalée", "Une étape d’entretien a été signalée pour votre démarche externe."),
        "successful": ("Résultat externe positif", "Un résultat externe positif a été enregistré pour votre démarche."),
        "unsuccessful": ("Résultat externe enregistré", "Un résultat externe défavorable a été enregistré pour votre démarche."),
        "withdrawn": ("Démarche externe retirée", "La démarche externe a été indiquée comme retirée."),
    }
    if outcome not in copy:
        return
    title, message = copy[outcome]
    _notify(
        event=event,
        recipient=context.journey.beneficiary,
        category=NotificationCategory.SERVICE,
        template_key=f"service.outcome.{outcome}",
        title=title,
        message=message,
        journey=context.journey,
        activity=context.journey.activity,
        metadata={"journey_id": str(context.journey_id), "context_id": str(context.pk), "outcome": outcome},
        action_url=_journey_action(context.journey),
    )


def _opportunity_recipients(opportunity, *, revision=None):
    recipients = {}
    contexts = ServiceJourneyContext.objects.filter(
        opportunity=opportunity,
        journey__status__in=ACTIVE_CASE_STATUSES,
        journey__beneficiary__is_active=True,
    ).select_related("journey__beneficiary", "opportunity_revision")
    if revision is not None:
        contexts = contexts.exclude(opportunity_revision=revision)
    for context in contexts:
        recipients[context.journey.beneficiary_id] = (context.journey.beneficiary, context.journey)
    for saved in OpportunitySave.objects.filter(opportunity=opportunity, profile__is_active=True).select_related("profile"):
        recipients.setdefault(saved.profile_id, (saved.profile, None))
    return recipients.values()


def _notify_opportunity_revision(event):
    revision_id = (event.payload or {}).get("revision_id")
    revision = (
        OpportunityRevision.objects.select_related("opportunity")
        .filter(pk=revision_id, published_at__isnull=False)
        .first()
    )
    if not revision:
        return
    for recipient, journey in _opportunity_recipients(revision.opportunity, revision=revision):
        _notify(
            event=event,
            recipient=recipient,
            category=NotificationCategory.OPPORTUNITY,
            template_key="opportunity.revision.available",
            title="Une nouvelle version est disponible",
            message="Une nouvelle version de cette opportunité est disponible. Votre dossier existant n’a pas été modifié automatiquement.",
            journey=journey,
            activity=journey.activity if journey else None,
            metadata={"opportunity_id": str(revision.opportunity_id), "revision_id": str(revision.pk)},
            action_url=_journey_action(journey) if journey else "",
        )


def _notify_opportunity_withdrawn(event):
    opportunity_id = (event.payload or {}).get("opportunity_id")
    opportunity = Opportunity.objects.filter(pk=opportunity_id).first()
    if not opportunity:
        return
    for recipient, journey in _opportunity_recipients(opportunity):
        _notify(
            event=event,
            recipient=recipient,
            category=NotificationCategory.OPPORTUNITY,
            template_key="opportunity.withdrawn",
            title="Une opportunité suivie a été retirée",
            message="Une opportunité liée à votre suivi a été retirée. Vos dossiers existants ne sont pas modifiés automatiquement.",
            journey=journey,
            activity=journey.activity if journey else None,
            metadata={"opportunity_id": str(opportunity.pk)},
            action_url=_journey_action(journey) if journey else "",
        )


def _notify_source_changed(event):
    opportunity_id = (event.payload or {}).get("opportunity_id")
    if not opportunity_id:
        return
    seen = set()
    mandates = (
        Mandate.objects.filter(
            scope_type=AuthorityScope.PLATFORM,
            status=MandateStatus.ACTIVE,
            profile__is_active=True,
        )
        .select_related("profile", "role")
        .order_by("profile_id")
    )
    for mandate in mandates:
        recipient = mandate.profile
        if recipient.pk in seen:
            continue
        seen.add(recipient.pk)
        if not can(recipient, PermissionCode.OPPORTUNITIES_SOURCES_VERIFY):
            continue
        _notify(
            event=event,
            recipient=recipient,
            category=NotificationCategory.OPPORTUNITY,
            template_key="opportunity.source.changed",
            title="Une source Opportunity a changé",
            message="Une source Opportunity nécessite une nouvelle vérification de curation.",
            metadata={"opportunity_id": str(opportunity_id)},
        )


def consume_services_opportunity_event(event):
    handlers = {
        DomainEventType.JOURNEY_IN_PROGRESS: _notify_journey_started,
        DomainEventType.JOURNEY_STEP_READY: _notify_step,
        DomainEventType.JOURNEY_STEP_BLOCKED: _notify_step,
        DomainEventType.JOURNEY_ASSIGNMENT_CREATED: _notify_assignment,
        DomainEventType.JOURNEY_ASSIGNMENT_ENDED: _notify_assignment,
        DomainEventType.JOURNEY_ARTIFACT_REVIEW_REQUESTED: _notify_review,
        DomainEventType.JOURNEY_ARTIFACT_REVIEW_COMPLETED: _notify_review,
        DomainEventType.PAYMENT_OBLIGATION_CREATED: _notify_payment_obligation,
        DomainEventType.PAYMENT_EVIDENCE_SUBMITTED: _notify_payment_evidence,
        DomainEventType.PAYMENT_EVIDENCE_VERIFIED: _notify_payment_evidence,
        DomainEventType.PAYMENT_EVIDENCE_REJECTED: _notify_payment_evidence,
        DomainEventType.SERVICE_SUBMISSION_SUBMITTED: _notify_submission,
        DomainEventType.SERVICE_SUBMISSION_ACKNOWLEDGED: _notify_submission,
        DomainEventType.SERVICE_SUBMISSION_FAILED: _notify_submission,
        DomainEventType.SERVICE_SUBMISSION_WITHDRAWN: _notify_submission,
        DomainEventType.SERVICE_OUTCOME_CHANGED: _notify_outcome,
        DomainEventType.OPPORTUNITY_REVISION_PUBLISHED: _notify_opportunity_revision,
        DomainEventType.OPPORTUNITY_WITHDRAWN: _notify_opportunity_withdrawn,
        DomainEventType.OPPORTUNITY_SOURCE_CHANGED: _notify_source_changed,
    }
    handler = handlers.get(event.event_type)
    if handler:
        handler(event)


register_consumer(CONSUMER_NAME, consume_services_opportunity_event, event_types=EVENT_TYPES)
