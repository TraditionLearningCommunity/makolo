from __future__ import annotations

from dataclasses import dataclass

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from access.models import Access
from domain_events.contracts import DomainEventType
from journeys.collaboration_models import JourneyBlocker, JourneyStep
from journeys.models import Journey, TERMINAL_JOURNEY_STATUSES
from notifications.models import NotificationCategory, NotificationKind
from notifications.services import create_notification
from opportunities.models import Opportunity, OpportunityPublicationStatus, OpportunitySave
from payments.models import PaymentObligation
from preparation.contextual_actions import (
    actions_from_action_advices,
    actions_from_prepared_start,
    actions_from_readiness,
    contextual_action_result_signature,
    resolve_contextual_actions,
)
from preparation.prepared_start import prepared_start_for_revision
from preparation.proactive_preparation import (
    NOTIFICATION_SIGNATURE_VERSION,
    proactive_notification_signature,
)
from readiness.resolver import resolve_journey_readiness
from readiness.selectors import participant_readiness_queryset
from spatiotemporal.hazards import get_action_advices, get_hazards

from .proactive_models import ProactivePreparationCursor, ProactivePreparationWatchKind


PROACTIVE_EVENT_LIMIT = 200

OWNER_NOTIFICATION_EVENT_TYPES = frozenset(
    {
        DomainEventType.OPPORTUNITY_REVISION_PUBLISHED,
        DomainEventType.OPPORTUNITY_WITHDRAWN,
        DomainEventType.JOURNEY_PENDING_PAYMENT,
        DomainEventType.JOURNEY_CONFIRMED,
        DomainEventType.JOURNEY_IN_PROGRESS,
        DomainEventType.JOURNEY_STEP_READY,
        DomainEventType.JOURNEY_STEP_BLOCKED,
        DomainEventType.FORM_REQUESTED,
        DomainEventType.FORM_REOPENED,
        DomainEventType.PAYMENT_OBLIGATION_CREATED,
        DomainEventType.PAYMENT_OBLIGATION_REFUNDED,
        DomainEventType.PAYMENT_SUCCEEDED,
        DomainEventType.PAYMENT_FAILED,
        DomainEventType.PAYMENT_REFUNDED,
        DomainEventType.ACCESS_ISSUED,
        DomainEventType.OCCURRENCE_RESCHEDULED,
        DomainEventType.OCCURRENCE_CANCELLED,
    }
)


@dataclass(frozen=True, slots=True)
class Evaluation:
    result: object
    watch_kind: str
    recipient: object
    opportunity_save: OpportunitySave | None = None
    journey: Journey | None = None
    revision_id: str | None = None
    owner_projection_covered: bool = False


@dataclass(frozen=True, slots=True)
class EvaluationOutcome:
    status: str
    projection_changed: bool = False
    material_changed: bool = False
    notification_created: bool = False
    notification_suppressed: bool = False
    stale_removed: bool = False


def _canonical_deadlines(journey: Journey):
    deadlines = {}
    if journey.expires_at is not None:
        deadlines["journey.status"] = journey.expires_at
    for step in journey.steps.all():
        if step.due_at is not None:
            deadlines[f"journey.step.{step.pk}"] = step.due_at
    for blocker in journey.blockers.all():
        if blocker.due_at is not None:
            deadlines[f"journey.blocker.{blocker.pk}"] = blocker.due_at
    for obligation in journey.payment_obligations.all():
        if obligation.due_at is not None:
            deadlines[f"payment_obligation.{obligation.pk}"] = obligation.due_at
    for request in journey.form_requests.all():
        if request.due_at is not None:
            deadlines[f"form_request.{request.pk}"] = request.due_at
    return deadlines


def _provider_free_m6_actions(journey: Journey, *, observed_at):
    occurrence = journey.occurrence
    if occurrence is None:
        return (), False
    hazards = get_hazards(occurrence=occurrence, journey=journey, mobility=None, now=observed_at)
    advices = get_action_advices(
        occurrence=occurrence,
        journey=journey,
        mobility=None,
        hazards=hazards,
        now=observed_at,
    )
    owner_covered = any(hazard.kind in {"occurrence_cancelled", "access_changed"} for hazard in hazards)
    return (
        actions_from_action_advices(advices, context_type="journey", context_id=str(journey.pk)),
        owner_covered,
    )


def evaluate_saved_opportunity(saved: OpportunitySave, *, observed_at=None) -> Evaluation | None:
    observed_at = observed_at or timezone.now()
    saved = (
        OpportunitySave.objects.select_related("profile", "opportunity__current_revision")
        .filter(pk=saved.pk)
        .first()
    )
    if saved is None or not saved.profile.is_active:
        return None
    opportunity = saved.opportunity
    revision = opportunity.current_revision
    if opportunity.publication_status != OpportunityPublicationStatus.PUBLISHED or revision is None:
        return None
    try:
        prepared = prepared_start_for_revision(actor=saved.profile, revision=revision, observed_at=observed_at)
    except (PermissionDenied, ValidationError):
        return None
    result = resolve_contextual_actions(actions_from_prepared_start(prepared), observed_at=observed_at)
    return Evaluation(
        result=result,
        watch_kind=ProactivePreparationWatchKind.OPPORTUNITY,
        recipient=saved.profile,
        opportunity_save=saved,
        revision_id=str(revision.pk),
    )


def _authorized_journey(journey: Journey):
    if not journey.beneficiary_id or not journey.beneficiary.is_active:
        return None
    return participant_readiness_queryset(
        journey.beneficiary,
        Journey.objects.filter(pk=journey.pk),
    ).first()


def evaluate_journey(journey: Journey, *, observed_at=None) -> Evaluation | None:
    observed_at = observed_at or timezone.now()
    journey = Journey.objects.select_related("beneficiary").filter(pk=journey.pk).first()
    if journey is None:
        return None
    authorized = _authorized_journey(journey)
    if authorized is None:
        return None
    try:
        readiness = resolve_journey_readiness(
            authorized,
            viewer=authorized.beneficiary,
            observed_at=observed_at,
        )
    except PermissionDenied:
        return None
    actions = list(
        actions_from_readiness(
            readiness,
            context_type="journey",
            context_id=str(authorized.pk),
            canonical_deadlines=_canonical_deadlines(authorized),
        )
    )
    m6_actions, m6_owner_covered = _provider_free_m6_actions(
        authorized,
        observed_at=observed_at,
    )
    actions.extend(m6_actions)
    result = resolve_contextual_actions(actions, observed_at=observed_at)
    return Evaluation(
        result=result,
        watch_kind=ProactivePreparationWatchKind.JOURNEY,
        recipient=authorized.beneficiary,
        journey=authorized,
        owner_projection_covered=m6_owner_covered,
    )


def _cursor_lookup(evaluation: Evaluation):
    if evaluation.watch_kind == ProactivePreparationWatchKind.OPPORTUNITY:
        return {
            "recipient": evaluation.recipient,
            "opportunity_save": evaluation.opportunity_save,
            "watch_kind": ProactivePreparationWatchKind.OPPORTUNITY,
        }
    return {
        "recipient": evaluation.recipient,
        "journey": evaluation.journey,
        "watch_kind": ProactivePreparationWatchKind.JOURNEY,
    }


def _notification_copy(evaluation: Evaluation):
    if evaluation.watch_kind == ProactivePreparationWatchKind.OPPORTUNITY:
        return (
            NotificationCategory.OPPORTUNITY,
            "Votre préparation a changé",
            "La prochaine action utile pour cette opportunité a changé.",
            "",
        )
    category = (
        NotificationCategory.SERVICE
        if evaluation.journey.workflow == "service"
        else NotificationCategory.SYSTEM
    )
    return (
        category,
        "Votre préparation a changé",
        "La prochaine action utile pour votre démarche a changé.",
        reverse("core:participant-journey-detail", kwargs={"pk": evaluation.journey.pk}),
    )


def _notification_metadata(evaluation: Evaluation, sequence: int):
    data = {
        "watch_kind": evaluation.watch_kind,
        "transition_sequence": sequence,
    }
    if evaluation.opportunity_save is not None:
        data["opportunity_id"] = str(evaluation.opportunity_save.opportunity_id)
        if evaluation.revision_id:
            data["revision_id"] = evaluation.revision_id
    if evaluation.journey is not None:
        data["journey_id"] = str(evaluation.journey.pk)
    return data


def apply_evaluation(
    evaluation: Evaluation,
    *,
    observed_at=None,
    domain_event=None,
    force_silent_rebaseline=False,
) -> EvaluationOutcome:
    observed_at = observed_at or timezone.now()
    projection_signature = contextual_action_result_signature(evaluation.result)
    notification_signature = proactive_notification_signature(evaluation.result)
    lookup = _cursor_lookup(evaluation)

    with transaction.atomic():
        cursor, created = ProactivePreparationCursor.objects.get_or_create(
            **lookup,
            defaults={
                "projection_signature": projection_signature,
                "notification_signature": notification_signature,
                "signature_version": NOTIFICATION_SIGNATURE_VERSION,
                "last_evaluated_at": observed_at,
            },
        )
        cursor = ProactivePreparationCursor.objects.select_for_update().get(pk=cursor.pk)
        if created:
            return EvaluationOutcome(status="baseline")

        if cursor.signature_version != NOTIFICATION_SIGNATURE_VERSION:
            cursor.projection_signature = projection_signature
            cursor.notification_signature = notification_signature
            cursor.signature_version = NOTIFICATION_SIGNATURE_VERSION
            cursor.last_evaluated_at = observed_at
            cursor.save(
                update_fields=[
                    "projection_signature",
                    "notification_signature",
                    "signature_version",
                    "last_evaluated_at",
                    "updated_at",
                ]
            )
            return EvaluationOutcome(status="rebaseline")

        projection_changed = cursor.projection_signature != projection_signature
        if not projection_changed:
            cursor.last_evaluated_at = observed_at
            cursor.save(update_fields=["last_evaluated_at", "updated_at"])
            return EvaluationOutcome(status="unchanged")

        cursor.projection_signature = projection_signature
        cursor.last_evaluated_at = observed_at
        notification_changed = cursor.notification_signature != notification_signature
        if not notification_changed:
            cursor.save(update_fields=["projection_signature", "last_evaluated_at", "updated_at"])
            return EvaluationOutcome(status="projection_only", projection_changed=True)

        cursor.notification_signature = notification_signature
        cursor.transition_sequence += 1
        sequence = cursor.transition_sequence
        event_type = getattr(domain_event, "event_type", None)
        idempotency_key = str(getattr(domain_event, "idempotency_key", "") or "")
        payment_settlement_covered = bool(
            event_type == DomainEventType.PAYMENT_OBLIGATION_SATISFIED
            and (":satisfied:payment:" in idempotency_key or ":satisfied:evidence:" in idempotency_key)
        )
        suppressed = bool(
            force_silent_rebaseline
            or evaluation.owner_projection_covered
            or event_type in OWNER_NOTIFICATION_EVENT_TYPES
            or payment_settlement_covered
        )
        if suppressed:
            cursor.save(
                update_fields=[
                    "projection_signature",
                    "notification_signature",
                    "transition_sequence",
                    "last_evaluated_at",
                    "updated_at",
                ]
            )
            return EvaluationOutcome(
                status="material_suppressed",
                projection_changed=True,
                material_changed=True,
                notification_suppressed=True,
            )

        category, title, message, action_url = _notification_copy(evaluation)
        notification = create_notification(
            recipient=evaluation.recipient,
            kind=NotificationKind.SYSTEM,
            category=category,
            title=title,
            message=message,
            action_url=action_url,
            dedup_key=f"proactive-preparation:{cursor.pk}:{sequence}",
            metadata=_notification_metadata(evaluation, sequence),
            domain_event=domain_event,
            journey=evaluation.journey,
            activity=evaluation.journey.activity if evaluation.journey is not None else None,
            template_key="preparation.proactive",
        )
        cursor.last_notified_at = observed_at
        cursor.save(
            update_fields=[
                "projection_signature",
                "notification_signature",
                "transition_sequence",
                "last_evaluated_at",
                "last_notified_at",
                "updated_at",
            ]
        )
        return EvaluationOutcome(
            status="notified",
            projection_changed=True,
            material_changed=True,
            notification_created=notification is not None,
        )


def remove_stale_cursor(cursor: ProactivePreparationCursor) -> bool:
    if cursor.watch_kind == ProactivePreparationWatchKind.OPPORTUNITY:
        saved = (
            OpportunitySave.objects.select_related("profile", "opportunity")
            .filter(pk=cursor.opportunity_save_id)
            .first()
        )
        stale = bool(
            saved is None
            or saved.profile_id != cursor.recipient_id
            or not saved.profile.is_active
            or saved.opportunity.publication_status != OpportunityPublicationStatus.PUBLISHED
        )
    else:
        journey = Journey.objects.select_related("beneficiary").filter(pk=cursor.journey_id).first()
        stale = bool(
            journey is None
            or not journey.beneficiary_id
            or journey.beneficiary_id != cursor.recipient_id
            or not journey.beneficiary.is_active
        )
    if stale:
        cursor.delete()
    return stale


def reevaluate_cursor(cursor: ProactivePreparationCursor, *, observed_at=None, domain_event=None):
    observed_at = observed_at or timezone.now()
    if remove_stale_cursor(cursor):
        return EvaluationOutcome(status="stale_removed", stale_removed=True)
    if cursor.watch_kind == ProactivePreparationWatchKind.OPPORTUNITY:
        evaluation = evaluate_saved_opportunity(cursor.opportunity_save, observed_at=observed_at)
    else:
        evaluation = evaluate_journey(cursor.journey, observed_at=observed_at)
    if evaluation is None:
        cursor.delete()
        return EvaluationOutcome(status="stale_removed", stale_removed=True)
    outcome = apply_evaluation(evaluation, observed_at=observed_at, domain_event=domain_event)
    if evaluation.journey is not None and evaluation.journey.status in TERMINAL_JOURNEY_STATUSES:
        ProactivePreparationCursor.objects.filter(pk=cursor.pk).delete()
    return outcome


def _stats():
    return {
        "watches_checked": 0,
        "baselines_created": 0,
        "projection_changes": 0,
        "material_changes": 0,
        "notifications_created": 0,
        "notifications_suppressed": 0,
        "stale_watches_removed": 0,
    }


def _count(stats, outcome: EvaluationOutcome):
    stats["watches_checked"] += 1
    if outcome.status == "baseline":
        stats["baselines_created"] += 1
    if outcome.projection_changed:
        stats["projection_changes"] += 1
    if outcome.material_changed:
        stats["material_changes"] += 1
    if outcome.notification_created:
        stats["notifications_created"] += 1
    if outcome.notification_suppressed:
        stats["notifications_suppressed"] += 1
    if outcome.stale_removed:
        stats["stale_watches_removed"] += 1


def _cycle_candidates(*, limit):
    existing_saves = ProactivePreparationCursor.objects.filter(
        opportunity_save__isnull=False
    ).values_list("opportunity_save_id", flat=True)
    saves = list(
        OpportunitySave.objects.filter(
            profile__is_active=True,
            opportunity__publication_status=OpportunityPublicationStatus.PUBLISHED,
            opportunity__current_revision__isnull=False,
        )
        .exclude(pk__in=existing_saves)
        .select_related("profile", "opportunity__current_revision")
        .order_by("created_at", "id")[:limit]
    )
    existing_journeys = ProactivePreparationCursor.objects.filter(
        journey__isnull=False
    ).values_list("journey_id", flat=True)
    journeys = list(
        Journey.objects.filter(beneficiary__isnull=False, beneficiary__is_active=True)
        .exclude(status__in=TERMINAL_JOURNEY_STATUSES)
        .exclude(pk__in=existing_journeys)
        .select_related("beneficiary")
        .order_by("created_at", "id")[:limit]
    )
    cursors = list(
        ProactivePreparationCursor.objects.select_related(
            "recipient",
            "opportunity_save__profile",
            "opportunity_save__opportunity__current_revision",
            "journey__beneficiary",
        )
        .order_by("last_evaluated_at", "id")[:limit]
    )
    candidates = [
        (cursor.last_evaluated_at, 0, str(cursor.pk), "cursor", cursor)
        for cursor in cursors
    ]
    candidates.extend(
        (saved.created_at, 1, str(saved.pk), "opportunity", saved)
        for saved in saves
    )
    candidates.extend(
        (journey.created_at, 2, str(journey.pk), "journey", journey)
        for journey in journeys
    )
    candidates.sort(key=lambda item: item[:3])
    return candidates[:limit]


def run_proactive_preparation_cycle(*, now=None, limit=200):
    """Bounded provider-free R3 safety net inside the existing Autopilot cadence."""
    now = now or timezone.now()
    limit = max(int(limit or 0), 0)
    stats = _stats()
    if limit == 0:
        return stats

    for _, _, _, kind, item in _cycle_candidates(limit=limit):
        if kind == "cursor":
            outcome = reevaluate_cursor(item, observed_at=now)
        elif kind == "opportunity":
            evaluation = evaluate_saved_opportunity(item, observed_at=now)
            if evaluation is None:
                continue
            outcome = apply_evaluation(evaluation, observed_at=now)
        else:
            evaluation = evaluate_journey(item, observed_at=now)
            if evaluation is None:
                continue
            outcome = apply_evaluation(evaluation, observed_at=now)
        _count(stats, outcome)
    return stats


def _journey_ids_for_event(event):
    payload = event.payload or {}
    journey_id = payload.get("journey_id")
    if journey_id:
        return [journey_id]
    step_id = payload.get("step_id")
    if step_id:
        value = JourneyStep.objects.filter(pk=step_id).values_list("journey_id", flat=True).first()
        return [value] if value else []
    blocker_id = payload.get("blocker_id")
    if blocker_id:
        value = JourneyBlocker.objects.filter(pk=blocker_id).values_list("journey_id", flat=True).first()
        return [value] if value else []
    obligation_id = payload.get("obligation_id")
    if obligation_id:
        value = PaymentObligation.objects.filter(pk=obligation_id).values_list("journey_id", flat=True).first()
        return [value] if value else []
    access_id = payload.get("access_id")
    if access_id:
        value = Access.objects.filter(pk=access_id).values_list("journey_id", flat=True).first()
        return [value] if value else []
    occurrence_id = payload.get("occurrence_id")
    if occurrence_id:
        return list(
            ProactivePreparationCursor.objects.filter(
                watch_kind=ProactivePreparationWatchKind.JOURNEY,
                journey__occurrence_id=occurrence_id,
            )
            .order_by("last_evaluated_at", "id")
            .values_list("journey_id", flat=True)[:PROACTIVE_EVENT_LIMIT]
        )
    return []


def reevaluate_for_domain_event(event):
    """Use event payload only for routing; canonical state is always re-read."""
    now = timezone.now()
    payload = event.payload or {}
    if event.event_type in {
        DomainEventType.OPPORTUNITY_REVISION_PUBLISHED,
        DomainEventType.OPPORTUNITY_WITHDRAWN,
    }:
        opportunity_id = payload.get("opportunity_id")
        if not opportunity_id:
            return
        opportunity = Opportunity.objects.filter(pk=opportunity_id).first()
        if opportunity is None:
            return
        cursors = list(
            ProactivePreparationCursor.objects.filter(
                watch_kind=ProactivePreparationWatchKind.OPPORTUNITY,
                opportunity_save__opportunity_id=opportunity.pk,
            )
            .select_related(
                "opportunity_save__profile",
                "opportunity_save__opportunity__current_revision",
            )
            .order_by("last_evaluated_at", "id")[:PROACTIVE_EVENT_LIMIT]
        )
        for cursor in cursors:
            evaluation = evaluate_saved_opportunity(cursor.opportunity_save, observed_at=now)
            if evaluation is None:
                remove_stale_cursor(cursor)
                continue
            apply_evaluation(
                evaluation,
                observed_at=now,
                domain_event=event,
                force_silent_rebaseline=(
                    event.event_type == DomainEventType.OPPORTUNITY_REVISION_PUBLISHED
                ),
            )
        return

    for journey_id in _journey_ids_for_event(event)[:PROACTIVE_EVENT_LIMIT]:
        cursor = (
            ProactivePreparationCursor.objects.filter(
                watch_kind=ProactivePreparationWatchKind.JOURNEY,
                journey_id=journey_id,
            )
            .select_related("journey__beneficiary")
            .first()
        )
        if cursor is not None:
            reevaluate_cursor(cursor, observed_at=now, domain_event=event)
