from datetime import timedelta

from django.urls import reverse
from django.utils import timezone

from journeys.collaboration_models import JourneyBlocker, JourneyBlockerStatus, JourneyStep, JourneyStepStatus
from journeys.models import Journey, TERMINAL_JOURNEY_STATUSES, WorkflowKind
from notifications.models import NotificationCategory, NotificationKind
from notifications.services import create_notification
from opportunities.models import OpportunityPublicationStatus, OpportunityRevision, OpportunitySave
from payments.models import PaymentObligation, PaymentObligationStatus

from .models import AutomationRun, AutomationRunStatus


MILESTONE_GRACE = timedelta(hours=1)
OPPORTUNITY_DEADLINE_MILESTONES = ((30, "J-30"), (14, "J-14"), (7, "J-7"), (3, "J-3"), (1, "J-1"), (0, "J"))
JOURNEY_EXPIRY_MILESTONES = ((7, "J-7"), (3, "J-3"), (1, "J-1"), (0, "J"))
STEP_DUE_MILESTONES = ((7, "J-7"), (3, "J-3"), (1, "J-1"), (0, "J"))
BLOCKER_DUE_MILESTONES = ((3, "J-3"), (1, "J-1"), (0, "J"))
PAYMENT_DUE_MILESTONES = ((7, "J-7"), (3, "J-3"), (1, "J-1"), (0, "J"))


def _target_key(value):
    return value.isoformat().replace("+00:00", "Z")


def _current_milestone(target, now, milestones, *, allow_overdue=False):
    for days, label in milestones:
        starts = target - timedelta(days=days)
        if starts <= now < starts + MILESTONE_GRACE:
            return label
    if allow_overdue and now >= target + MILESTONE_GRACE:
        return "overdue"
    return None


def _journey_action(journey):
    return reverse("core:participant-journey-detail", kwargs={"pk": journey.pk})


def _create_once(*, target_type, target_id, target_at, milestone, recipient, category, title, message, journey=None, metadata=None):
    dedup = f"service-reminder:{target_type}:{target_id}:{_target_key(target_at)}:{milestone}:{recipient.pk}"[:255]
    run, created = AutomationRun.objects.get_or_create(
        dedup_key=dedup,
        defaults={
            "event": None,
            "rule_key": f"service-reminder:{target_type}:{milestone}"[:80],
            "status": AutomationRunStatus.SUCCESS,
            "summary": f"Rappel {target_type} {milestone}"[:255],
            "payload": {
                "target_type": target_type,
                "target_id": str(target_id),
                "target_at": target_at.isoformat(),
                "milestone": milestone,
                "recipient_id": str(recipient.pk),
            },
        },
    )
    if not created:
        return 0
    create_notification(
        recipient=recipient,
        kind=NotificationKind.SYSTEM,
        category=category,
        title=title,
        message=message,
        action_url=_journey_action(journey) if journey else "",
        dedup_key=f"notification:{dedup}"[:255],
        metadata={
            "automation_run_id": str(run.pk),
            "target_type": target_type,
            "target_id": str(target_id),
            **(metadata or {}),
        },
        activity=journey.activity if journey else None,
        journey=journey,
        template_key=f"service.reminder.{target_type}",
    )
    return 1


def _run_opportunity_opening(now):
    created = 0
    revisions = (
        OpportunityRevision.objects.filter(
            opportunity__publication_status=OpportunityPublicationStatus.PUBLISHED,
            opportunity__current_revision_id=models.F("pk"),
            published_at__isnull=False,
            opens_at__isnull=False,
            opens_at__lte=now,
        )
        .select_related("opportunity")
        .order_by("opens_at", "pk")
    )
    for revision in revisions:
        for saved in OpportunitySave.objects.filter(
            opportunity=revision.opportunity,
            profile__is_active=True,
            created_at__lte=revision.opens_at,
        ).select_related("profile"):
            created += _create_once(
                target_type="opportunity-opening",
                target_id=revision.pk,
                target_at=revision.opens_at,
                milestone="open",
                recipient=saved.profile,
                category=NotificationCategory.OPPORTUNITY,
                title="Une opportunité suivie est maintenant ouverte",
                message="Une opportunité que vous suivez est maintenant ouverte.",
                metadata={"opportunity_id": str(revision.opportunity_id), "revision_id": str(revision.pk)},
            )
    return created


def _run_opportunity_deadlines(now):
    created = 0
    revisions = (
        OpportunityRevision.objects.filter(
            opportunity__publication_status=OpportunityPublicationStatus.PUBLISHED,
            opportunity__current_revision_id=models.F("pk"),
            published_at__isnull=False,
            deadline_at__isnull=False,
        )
        .select_related("opportunity")
        .order_by("deadline_at", "pk")
    )
    for revision in revisions:
        milestone = _current_milestone(revision.deadline_at, now, OPPORTUNITY_DEADLINE_MILESTONES)
        if not milestone:
            continue
        for saved in OpportunitySave.objects.filter(opportunity=revision.opportunity, profile__is_active=True).select_related("profile"):
            created += _create_once(
                target_type="opportunity-deadline",
                target_id=revision.pk,
                target_at=revision.deadline_at,
                milestone=milestone,
                recipient=saved.profile,
                category=NotificationCategory.OPPORTUNITY,
                title=f"Échéance Opportunity — {milestone}",
                message="L’échéance d’une opportunité que vous suivez approche.",
                metadata={"opportunity_id": str(revision.opportunity_id), "revision_id": str(revision.pk)},
            )
    return created


def _run_journey_expiry(now):
    created = 0
    journeys = (
        Journey.objects.filter(
            workflow=WorkflowKind.SERVICE,
            beneficiary__is_active=True,
            expires_at__isnull=False,
        )
        .exclude(status__in=TERMINAL_JOURNEY_STATUSES)
        .select_related("beneficiary", "activity")
        .order_by("expires_at", "pk")
    )
    for journey in journeys:
        milestone = _current_milestone(journey.expires_at, now, JOURNEY_EXPIRY_MILESTONES)
        if not milestone:
            continue
        created += _create_once(
            target_type="journey-expiry",
            target_id=journey.pk,
            target_at=journey.expires_at,
            milestone=milestone,
            recipient=journey.beneficiary,
            category=NotificationCategory.SERVICE,
            title=f"Échéance de votre démarche — {milestone}",
            message="L’échéance de votre démarche approche.",
            journey=journey,
        )
    return created


def _run_step_due(now):
    created = 0
    steps = (
        JourneyStep.objects.filter(
            journey__workflow=WorkflowKind.SERVICE,
            journey__beneficiary__is_active=True,
            due_at__isnull=False,
        )
        .exclude(status__in={JourneyStepStatus.COMPLETED, JourneyStepStatus.SKIPPED, JourneyStepStatus.CANCELLED})
        .select_related("journey__beneficiary", "journey__activity")
        .order_by("due_at", "pk")
    )
    for step in steps:
        milestone = _current_milestone(step.due_at, now, STEP_DUE_MILESTONES, allow_overdue=True)
        if not milestone:
            continue
        title = "Étape en retard" if milestone == "overdue" else f"Échéance d’une étape — {milestone}"
        message = "Une étape de votre démarche est en retard." if milestone == "overdue" else "Une étape de votre démarche arrive à échéance."
        created += _create_once(
            target_type="step",
            target_id=step.pk,
            target_at=step.due_at,
            milestone=milestone,
            recipient=step.journey.beneficiary,
            category=NotificationCategory.SERVICE,
            title=title,
            message=message,
            journey=step.journey,
            metadata={"step_id": str(step.pk)},
        )
    return created


def _run_blocker_due(now):
    created = 0
    blockers = (
        JourneyBlocker.objects.filter(
            journey__workflow=WorkflowKind.SERVICE,
            journey__beneficiary__is_active=True,
            status=JourneyBlockerStatus.ACTIVE,
            due_at__isnull=False,
        )
        .select_related("journey__beneficiary", "journey__activity")
        .order_by("due_at", "pk")
    )
    for blocker in blockers:
        milestone = _current_milestone(blocker.due_at, now, BLOCKER_DUE_MILESTONES, allow_overdue=True)
        if not milestone:
            continue
        title = "Blocage en retard" if milestone == "overdue" else f"Échéance d’un blocage — {milestone}"
        message = "Un blocage de votre démarche nécessite votre attention."
        created += _create_once(
            target_type="blocker",
            target_id=blocker.pk,
            target_at=blocker.due_at,
            milestone=milestone,
            recipient=blocker.journey.beneficiary,
            category=NotificationCategory.SERVICE,
            title=title,
            message=message,
            journey=blocker.journey,
            metadata={"blocker_id": str(blocker.pk)},
        )
    return created


def _run_payment_due(now):
    created = 0
    obligations = (
        PaymentObligation.objects.filter(
            journey__workflow=WorkflowKind.SERVICE,
            journey__beneficiary__is_active=True,
            due_at__isnull=False,
            status__in={PaymentObligationStatus.PENDING, PaymentObligationStatus.PROCESSING},
        )
        .select_related("journey__beneficiary", "journey__activity")
        .order_by("due_at", "pk")
    )
    for obligation in obligations:
        milestone = _current_milestone(obligation.due_at, now, PAYMENT_DUE_MILESTONES, allow_overdue=True)
        if not milestone:
            continue
        title = "Paiement en retard" if milestone == "overdue" else f"Échéance de paiement — {milestone}"
        message = (
            f"Une obligation de {obligation.amount} {obligation.currency} est en retard."
            if milestone == "overdue"
            else f"Une obligation de {obligation.amount} {obligation.currency} arrive à échéance."
        )
        created += _create_once(
            target_type="payment-obligation",
            target_id=obligation.pk,
            target_at=obligation.due_at,
            milestone=milestone,
            recipient=obligation.journey.beneficiary,
            category=NotificationCategory.SERVICE,
            title=title,
            message=message,
            journey=obligation.journey,
            metadata={"obligation_id": str(obligation.pk)},
        )
    return created


def run_service_reminders(*, now=None):
    now = now or timezone.now()
    return {
        "opportunity_opening": _run_opportunity_opening(now),
        "opportunity_deadline": _run_opportunity_deadlines(now),
        "journey_expiry": _run_journey_expiry(now),
        "step_due": _run_step_due(now),
        "blocker_due": _run_blocker_due(now),
        "payment_obligation_due": _run_payment_due(now),
    }
