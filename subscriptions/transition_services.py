from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from payments.models import PaymentObligation, PaymentObligationStatus
from requirements.contracts import RequirementAssessmentState, RequirementMode
from requirements.registry import RequirementConfigurationError, RequirementRegistryError, registry

from .contracts import (
    PlanEligibilityStatus,
    PlanVersionStatus,
    RequirementPhase,
    SubscriptionItemStatus,
    SubscriptionPlanType,
    SubscriptionStatus,
    SubscriptionTransitionKind,
    SubscriptionTransitionRequestOrigin,
    SubscriptionTransitionStatus,
)
from .eligibility import resolve_plan_eligibility
from .eligibility_models import PlanRequirement
from .models import PlanVersion
from .runtime_models import Subscription, SubscriptionItem
from .transition_models import (
    OPEN_TRANSITION_STATUSES,
    SubscriptionRequirementAssessment,
    SubscriptionRequirementAssessmentEvent,
    SubscriptionTransition,
    SubscriptionTransitionPaymentObligation,
)


SATISFIED_FINANCIAL_OBLIGATION_STATUSES = {
    PaymentObligationStatus.SATISFIED,
    PaymentObligationStatus.WAIVED,
}

TERMINAL_TRANSITION_STATUSES = {
    SubscriptionTransitionStatus.COMPLETED,
    SubscriptionTransitionStatus.REJECTED,
    SubscriptionTransitionStatus.CANCELLED,
    SubscriptionTransitionStatus.EXPIRED,
    SubscriptionTransitionStatus.FAILED,
}


class SubscriptionTransitionError(ValidationError):
    pass


def _actor_or_none(actor):
    return actor if getattr(actor, "is_authenticated", False) else None


def _set_transition_status(transition, status, *, reason=None, failure_code=None, at=None):
    at = at or timezone.now()
    transition.status = status
    if reason is not None:
        transition.reason = (reason or "")[:500]
    if failure_code is not None:
        transition.failure_code = (failure_code or "")[:120]
    if status == SubscriptionTransitionStatus.READY:
        transition.ready_at = transition.ready_at or at
    elif status == SubscriptionTransitionStatus.COMPLETED:
        transition.completed_at = transition.completed_at or at
    elif status == SubscriptionTransitionStatus.CANCELLED:
        transition.cancelled_at = transition.cancelled_at or at
    elif status == SubscriptionTransitionStatus.FAILED:
        transition.failed_at = transition.failed_at or at
    transition.save()
    return transition


def _assessment_value(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _record_assessment_state(
    assessment,
    *,
    state,
    reason_code,
    actual_value=None,
    expected_value=None,
    actor=None,
    note=None,
    evaluated_at=None,
):
    previous = assessment.state
    evaluated_at = evaluated_at or timezone.now()
    assessment.state = state
    assessment.reason_code = (reason_code or "")[:160]
    assessment.actual_value = _assessment_value(actual_value)
    assessment.expected_value = _assessment_value(expected_value)
    assessment.last_evaluated_at = evaluated_at
    assessment.assessed_at = evaluated_at
    if actor is not None:
        assessment.assessed_by = _actor_or_none(actor)
    if note is not None:
        assessment.note = (note or "")[:500]
    assessment.save()
    if previous != assessment.state:
        SubscriptionRequirementAssessmentEvent.objects.create(
            assessment=assessment,
            previous_state=previous,
            state=assessment.state,
            reason_code=assessment.reason_code,
            assessed_by=_actor_or_none(actor),
        )
    return assessment


def _evaluate_automatic_assessment(assessment):
    requirement = assessment.plan_requirement
    subject = assessment.transition.subscription.subject
    if requirement.mode != RequirementMode.AUTOMATIC:
        return assessment
    try:
        result = registry.evaluate(
            requirement.evaluator_key,
            subject=subject,
            config=requirement.config,
        )
    except (RequirementRegistryError, RequirementConfigurationError, ValueError) as exc:
        raise SubscriptionTransitionError(
            f"Requirement catalogue invalide: {requirement.key}: {exc}"
        ) from exc
    return _record_assessment_state(
        assessment,
        state=result.state,
        reason_code=result.reason_code,
        actual_value=result.actual_value,
        expected_value=result.expected_value,
        evaluated_at=result.observed_at,
    )


def _initialize_assessment(assessment):
    if assessment.plan_requirement.mode == RequirementMode.AUTOMATIC:
        return _evaluate_automatic_assessment(assessment)
    return _record_assessment_state(
        assessment,
        state=RequirementAssessmentState.PENDING,
        reason_code=f"requirement.{assessment.plan_requirement.mode}.pending",
    )


def _validate_origin(request_origin):
    if request_origin not in SubscriptionTransitionRequestOrigin.values:
        raise SubscriptionTransitionError("Origine de demande Subscription inconnue.")


def _existing_intent_matches_request(
    existing,
    *,
    kind,
    target_plan_version,
    source_item,
    request_origin,
):
    if existing.kind != kind or existing.request_origin != request_origin:
        return False
    if target_plan_version is not None and existing.target_plan_version_id != target_plan_version.pk:
        return False
    if kind in {SubscriptionTransitionKind.BASE_SWITCH, SubscriptionTransitionKind.ADDON_ADD}:
        return target_plan_version is not None and existing.source_item_id is None
    if kind == SubscriptionTransitionKind.ADDON_REMOVE:
        return source_item is not None and existing.source_item_id == source_item.pk
    return False


def _resolve_transition_intent(subscription, *, kind, target_plan_version=None, source_item=None):
    if kind not in SubscriptionTransitionKind.values:
        raise SubscriptionTransitionError("Type de Transition inconnu.")

    active = (
        SubscriptionItem.objects.select_for_update()
        .filter(subscription=subscription, status=SubscriptionItemStatus.ACTIVE)
        .select_related("plan", "plan_version")
    )

    if kind == SubscriptionTransitionKind.BASE_SWITCH:
        if target_plan_version is None:
            raise SubscriptionTransitionError("base_switch exige une PlanVersion cible.")
        source = active.filter(item_type=SubscriptionPlanType.BASE).first()
        if source is None:
            raise SubscriptionTransitionError(
                "La Subscription ne possède pas de BASE actif cohérent."
            )
        if source.plan_version_id == target_plan_version.pk:
            raise SubscriptionTransitionError("Le BASE cible est déjà actif.")
        return source.plan_version, None, target_plan_version

    if kind == SubscriptionTransitionKind.ADDON_ADD:
        if target_plan_version is None:
            raise SubscriptionTransitionError("addon_add exige une PlanVersion cible.")
        if active.filter(
            item_type=SubscriptionPlanType.ADDON,
            plan_id=target_plan_version.plan_id,
        ).exists():
            raise SubscriptionTransitionError("Cet add-on logique est déjà actif.")
        return None, None, target_plan_version

    if kind != SubscriptionTransitionKind.ADDON_REMOVE:
        raise SubscriptionTransitionError("Type de Transition inconnu.")
    if source_item is None:
        raise SubscriptionTransitionError("addon_remove exige l’Item actif à retirer.")
    source_item = active.filter(
        pk=source_item.pk,
        item_type=SubscriptionPlanType.ADDON,
    ).first()
    if source_item is None:
        raise SubscriptionTransitionError(
            "L’add-on à retirer n’est pas actif sur cette Subscription."
        )
    if (
        target_plan_version is not None
        and target_plan_version.pk != source_item.plan_version_id
    ):
        raise SubscriptionTransitionError(
            "addon_remove doit pinner la PlanVersion exacte de l’Item retiré."
        )
    return None, source_item, source_item.plan_version


def _validate_target(subscription, target_plan_version, kind):
    if target_plan_version.status != PlanVersionStatus.PUBLISHED:
        raise SubscriptionTransitionError(
            "Seule une PlanVersion publiée peut être demandée."
        )
    if not target_plan_version.plan.is_active:
        raise SubscriptionTransitionError("Un Plan inactif ne peut pas être demandé.")
    if target_plan_version.plan.subject_type != subscription.subject_type:
        raise SubscriptionTransitionError(
            "Le Plan cible ne correspond pas au sujet de la Subscription."
        )
    expected_type = (
        SubscriptionPlanType.BASE
        if kind == SubscriptionTransitionKind.BASE_SWITCH
        else SubscriptionPlanType.ADDON
    )
    if target_plan_version.plan.plan_type != expected_type:
        raise SubscriptionTransitionError(
            "Le type de Plan cible est incompatible avec la Transition."
        )


def _materialize_acquisition_requirements(transition):
    requirements = PlanRequirement.objects.filter(
        plan_version=transition.target_plan_version,
        phase=RequirementPhase.ACQUISITION,
    ).order_by("position", "key")
    assessments = []
    for requirement in requirements:
        assessment, created = SubscriptionRequirementAssessment.objects.get_or_create(
            transition=transition,
            plan_requirement=requirement,
        )
        if created or assessment.state == RequirementAssessmentState.UNASSESSED:
            _initialize_assessment(assessment)
        assessments.append(assessment)
    return assessments


@transaction.atomic
def request_subscription_transition(
    *,
    subscription,
    kind,
    target_plan_version=None,
    source_item=None,
    requested_by=None,
    request_origin=SubscriptionTransitionRequestOrigin.SELF_SERVICE,
    idempotency_key,
    expires_at=None,
    reason="",
):
    key = (idempotency_key or "").strip()
    if not key:
        raise SubscriptionTransitionError("Une clé d’idempotence est obligatoire.")
    _validate_origin(request_origin)

    subscription = (
        Subscription.objects.select_for_update(of=("self",))
        .select_related("profile", "space")
        .get(pk=subscription.pk)
    )
    if subscription.status == SubscriptionStatus.CLOSED:
        raise SubscriptionTransitionError(
            "Une Subscription fermée ne peut pas changer de formule."
        )

    requested_target = (
        PlanVersion.objects.select_for_update().select_related("plan").get(
            pk=target_plan_version.pk
        )
        if target_plan_version is not None
        else None
    )

    # Idempotency is resolved before re-reading mutable current items. This is
    # essential after completion: the target is now active by definition, but
    # a transport retry of the original POST must still return its Transition.
    existing = (
        SubscriptionTransition.objects.select_for_update()
        .filter(subscription=subscription, idempotency_key=key)
        .first()
    )
    if existing is not None:
        if not _existing_intent_matches_request(
            existing,
            kind=kind,
            target_plan_version=requested_target,
            source_item=source_item,
            request_origin=request_origin,
        ):
            raise SubscriptionTransitionError(
                "Cette clé d’idempotence correspond à une intention différente."
            )
        return existing

    source_plan_version, pinned_source_item, pinned_target = _resolve_transition_intent(
        subscription,
        kind=kind,
        target_plan_version=requested_target,
        source_item=source_item,
    )
    _validate_target(subscription, pinned_target, kind)

    if SubscriptionTransition.objects.select_for_update().filter(
        subscription=subscription,
        status__in=OPEN_TRANSITION_STATUSES,
    ).exists():
        raise SubscriptionTransitionError(
            "Une Transition mutante est déjà ouverte pour cette Subscription."
        )

    if kind != SubscriptionTransitionKind.ADDON_REMOVE:
        eligibility = resolve_plan_eligibility(
            subscription.subject,
            pinned_target,
            self_service=(
                request_origin == SubscriptionTransitionRequestOrigin.SELF_SERVICE
            ),
        )
        if eligibility.status in {
            PlanEligibilityStatus.NOT_ELIGIBLE,
            PlanEligibilityStatus.HIDDEN,
        }:
            raise SubscriptionTransitionError(
                "Cette PlanVersion ne peut pas être demandée dans ce contexte."
            )

    transition = SubscriptionTransition(
        subscription=subscription,
        kind=kind,
        source_plan_version=source_plan_version,
        target_plan_version=pinned_target,
        source_item=pinned_source_item,
        requested_by=_actor_or_none(requested_by),
        request_origin=request_origin,
        status=SubscriptionTransitionStatus.REQUESTED,
        expires_at=expires_at,
        reason=(reason or "")[:500],
        idempotency_key=key,
    )
    try:
        transition.save()
    except IntegrityError as exc:
        # The Subscription row lock normally serializes this path. Keep the DB
        # uniqueness constraint as the final authority if another writer races.
        concurrent = SubscriptionTransition.objects.filter(
            subscription=subscription,
            idempotency_key=key,
        ).first()
        if concurrent and _existing_intent_matches_request(
            concurrent,
            kind=kind,
            target_plan_version=pinned_target,
            source_item=pinned_source_item,
            request_origin=request_origin,
        ):
            return concurrent
        raise SubscriptionTransitionError(
            "Une Transition concurrente viole un invariant Subscription."
        ) from exc

    if kind != SubscriptionTransitionKind.ADDON_REMOVE:
        _materialize_acquisition_requirements(transition)
    _set_transition_status(transition, SubscriptionTransitionStatus.IN_PROGRESS)
    return evaluate_transition_readiness(transition=transition)


def _sync_payment_assessment_locked(assessment, *, actor=None):
    links = list(
        SubscriptionTransitionPaymentObligation.objects.filter(assessment=assessment)
        .select_related("obligation")
        .order_by("created_at", "id")
    )
    if not links:
        return _record_assessment_state(
            assessment,
            state=RequirementAssessmentState.PENDING,
            reason_code="requirement.payment.pending",
            actor=actor,
        )
    satisfied = all(
        link.obligation.status in SATISFIED_FINANCIAL_OBLIGATION_STATUSES
        for link in links
    )
    return _record_assessment_state(
        assessment,
        state=(
            RequirementAssessmentState.SATISFIED
            if satisfied
            else RequirementAssessmentState.PENDING
        ),
        reason_code=(
            "requirement.payment.satisfied"
            if satisfied
            else "requirement.payment.pending"
        ),
        actor=actor,
    )


@transaction.atomic
def link_transition_payment_obligation(*, assessment, obligation, actor=None):
    assessment = (
        SubscriptionRequirementAssessment.objects.select_for_update()
        .select_related("transition", "plan_requirement")
        .get(pk=assessment.pk)
    )
    obligation = PaymentObligation.objects.select_for_update().get(pk=obligation.pk)
    if assessment.plan_requirement.mode != RequirementMode.PAYMENT:
        raise SubscriptionTransitionError(
            "Seul un Requirement payment peut être lié à une PaymentObligation."
        )
    if assessment.transition.status not in OPEN_TRANSITION_STATUSES:
        raise SubscriptionTransitionError(
            "La Transition n’accepte plus de nouvelle obligation financière."
        )
    link, _ = SubscriptionTransitionPaymentObligation.objects.get_or_create(
        transition=assessment.transition,
        assessment=assessment,
        obligation=obligation,
        defaults={"created_by": _actor_or_none(actor)},
    )
    _sync_payment_assessment_locked(assessment, actor=actor)
    evaluate_transition_readiness(transition=assessment.transition)
    return link


@transaction.atomic
def sync_transition_payment_assessment(*, obligation, actor=None):
    obligation = PaymentObligation.objects.select_for_update().get(pk=obligation.pk)
    links = list(
        SubscriptionTransitionPaymentObligation.objects.select_for_update()
        .filter(obligation=obligation)
        .select_related("assessment__transition", "assessment__plan_requirement")
        .order_by("id")
    )
    transitions = {}
    for link in links:
        _sync_payment_assessment_locked(link.assessment, actor=actor)
        transitions[link.assessment.transition_id] = link.assessment.transition
    for transition in transitions.values():
        evaluate_transition_readiness(transition=transition)
    return tuple(link.assessment for link in links)


@transaction.atomic
def record_transition_requirement_decision(
    *, assessment, state, actor, reason_code, note=""
):
    assessment = (
        SubscriptionRequirementAssessment.objects.select_for_update()
        .select_related("transition", "plan_requirement")
        .get(pk=assessment.pk)
    )
    if assessment.transition.status not in OPEN_TRANSITION_STATUSES:
        raise SubscriptionTransitionError("Cette Transition est terminale.")
    if assessment.plan_requirement.mode in {
        RequirementMode.AUTOMATIC,
        RequirementMode.PAYMENT,
    }:
        raise SubscriptionTransitionError(
            "Cet Assessment est piloté automatiquement par son propriétaire canonique."
        )
    if state not in {
        RequirementAssessmentState.PENDING,
        RequirementAssessmentState.SATISFIED,
        RequirementAssessmentState.UNSATISFIED,
        RequirementAssessmentState.NOT_APPLICABLE,
    }:
        raise SubscriptionTransitionError("État manuel d’Assessment invalide.")
    if _actor_or_none(actor) is None:
        raise SubscriptionTransitionError(
            "Une décision manuelle exige un acteur authentifié explicite."
        )
    _record_assessment_state(
        assessment,
        state=state,
        reason_code=reason_code,
        actor=actor,
        note=note,
    )
    return evaluate_transition_readiness(transition=assessment.transition)


@transaction.atomic
def reevaluate_transition_requirements(*, transition):
    transition = SubscriptionTransition.objects.select_for_update().get(pk=transition.pk)
    if transition.status not in OPEN_TRANSITION_STATUSES:
        return transition
    assessments = list(
        SubscriptionRequirementAssessment.objects.select_for_update()
        .filter(transition=transition)
        .select_related(
            "plan_requirement",
            "transition__subscription__profile",
            "transition__subscription__space",
        )
        .order_by("plan_requirement__position", "id")
    )
    for assessment in assessments:
        if assessment.plan_requirement.mode == RequirementMode.AUTOMATIC:
            _evaluate_automatic_assessment(assessment)
        elif assessment.plan_requirement.mode == RequirementMode.PAYMENT:
            _sync_payment_assessment_locked(assessment)
    return evaluate_transition_readiness(transition=transition)


@transaction.atomic
def evaluate_transition_readiness(*, transition):
    transition = SubscriptionTransition.objects.select_for_update().get(pk=transition.pk)
    if transition.status in TERMINAL_TRANSITION_STATUSES:
        return transition
    now = timezone.now()
    if transition.expires_at and transition.expires_at <= now:
        return _set_transition_status(
            transition,
            SubscriptionTransitionStatus.EXPIRED,
            at=now,
        )

    assessments = list(
        SubscriptionRequirementAssessment.objects.filter(transition=transition)
        .select_related("plan_requirement")
        .order_by("plan_requirement__position", "id")
    )
    blocking = any(
        assessment.plan_requirement.is_mandatory
        and assessment.state
        not in {
            RequirementAssessmentState.SATISFIED,
            RequirementAssessmentState.NOT_APPLICABLE,
        }
        for assessment in assessments
    )
    if blocking:
        if transition.status == SubscriptionTransitionStatus.READY:
            transition.ready_at = None
        return _set_transition_status(
            transition,
            SubscriptionTransitionStatus.IN_PROGRESS,
        )
    return _set_transition_status(
        transition,
        SubscriptionTransitionStatus.READY,
        at=now,
    )


def _create_item_from_transition(*, transition, plan_version, at):
    item = SubscriptionItem(
        subscription=transition.subscription,
        plan=plan_version.plan,
        plan_version=plan_version,
        created_via_transition=transition,
        item_type=plan_version.plan.plan_type,
        status=SubscriptionItemStatus.ACTIVE,
        starts_at=at,
    )
    try:
        item.save()
    except IntegrityError as exc:
        raise SubscriptionTransitionError(
            "La completion concurrente viole un invariant SubscriptionItem."
        ) from exc
    return item


@transaction.atomic
def complete_subscription_transition(*, transition):
    transition = (
        SubscriptionTransition.objects.select_for_update()
        .select_related(
            "subscription",
            "source_plan_version__plan",
            "target_plan_version__plan",
            "source_item",
        )
        .get(pk=transition.pk)
    )
    if transition.status == SubscriptionTransitionStatus.COMPLETED:
        return transition
    if transition.status != SubscriptionTransitionStatus.READY:
        raise SubscriptionTransitionError(
            "Seule une Transition ready peut être complétée."
        )

    subscription = Subscription.objects.select_for_update().get(
        pk=transition.subscription_id
    )
    if subscription.status == SubscriptionStatus.CLOSED:
        raise SubscriptionTransitionError(
            "Une Subscription fermée ne peut pas appliquer une Transition."
        )
    transition.subscription = subscription
    now = timezone.now()

    if transition.kind == SubscriptionTransitionKind.BASE_SWITCH:
        current = (
            SubscriptionItem.objects.select_for_update()
            .filter(
                subscription=subscription,
                status=SubscriptionItemStatus.ACTIVE,
                item_type=SubscriptionPlanType.BASE,
            )
            .select_related("plan_version")
            .first()
        )
        if current is None or current.plan_version_id != transition.source_plan_version_id:
            raise SubscriptionTransitionError(
                "Le BASE actif a changé depuis la demande ; completion refusée."
            )
        current.status = SubscriptionItemStatus.ENDED
        current.ends_at = now
        current.ended_reason = f"subscription_transition:{transition.pk}"
        current.save(
            update_fields=["status", "ends_at", "ended_reason", "updated_at"]
        )
        _create_item_from_transition(
            transition=transition,
            plan_version=transition.target_plan_version,
            at=now,
        )

    elif transition.kind == SubscriptionTransitionKind.ADDON_ADD:
        if SubscriptionItem.objects.select_for_update().filter(
            subscription=subscription,
            status=SubscriptionItemStatus.ACTIVE,
            item_type=SubscriptionPlanType.ADDON,
            plan_id=transition.target_plan_version.plan_id,
        ).exists():
            raise SubscriptionTransitionError("Cet add-on logique est déjà actif.")
        _create_item_from_transition(
            transition=transition,
            plan_version=transition.target_plan_version,
            at=now,
        )

    elif transition.kind == SubscriptionTransitionKind.ADDON_REMOVE:
        item = SubscriptionItem.objects.select_for_update().filter(
            pk=transition.source_item_id,
            subscription=subscription,
        ).first()
        if item is None:
            raise SubscriptionTransitionError("L’Item ADDON pinné n’existe plus.")
        if item.status == SubscriptionItemStatus.ENDED:
            pass
        elif item.status != SubscriptionItemStatus.ACTIVE:
            raise SubscriptionTransitionError(
                "L’Item ADDON pinné n’est plus actif."
            )
        else:
            item.status = SubscriptionItemStatus.ENDED
            item.ends_at = now
            item.ended_reason = f"subscription_transition:{transition.pk}"
            item.save(
                update_fields=["status", "ends_at", "ended_reason", "updated_at"]
            )
    else:
        raise SubscriptionTransitionError("Type de Transition inconnu.")

    return _set_transition_status(
        transition,
        SubscriptionTransitionStatus.COMPLETED,
        at=now,
    )


@transaction.atomic
def cancel_subscription_transition(*, transition, actor=None, reason=""):
    transition = SubscriptionTransition.objects.select_for_update().get(pk=transition.pk)
    if transition.status == SubscriptionTransitionStatus.CANCELLED:
        return transition
    if transition.status not in OPEN_TRANSITION_STATUSES:
        raise SubscriptionTransitionError(
            "Cette Transition ne peut plus être annulée."
        )
    return _set_transition_status(
        transition,
        SubscriptionTransitionStatus.CANCELLED,
        reason=reason,
    )


@transaction.atomic
def reject_subscription_transition(
    *, transition, actor, reason, failure_code="requirement_rejected"
):
    transition = SubscriptionTransition.objects.select_for_update().get(pk=transition.pk)
    if transition.status == SubscriptionTransitionStatus.REJECTED:
        return transition
    if transition.status not in OPEN_TRANSITION_STATUSES:
        raise SubscriptionTransitionError(
            "Cette Transition ne peut plus être rejetée."
        )
    if _actor_or_none(actor) is None:
        raise SubscriptionTransitionError(
            "Un rejet exige un acteur authentifié explicite."
        )
    return _set_transition_status(
        transition,
        SubscriptionTransitionStatus.REJECTED,
        reason=reason,
        failure_code=failure_code,
    )


@transaction.atomic
def expire_subscription_transition(*, transition, at=None):
    transition = SubscriptionTransition.objects.select_for_update().get(pk=transition.pk)
    if transition.status == SubscriptionTransitionStatus.EXPIRED:
        return transition
    if transition.status not in OPEN_TRANSITION_STATUSES:
        raise SubscriptionTransitionError(
            "Cette Transition ne peut plus expirer."
        )
    at = at or timezone.now()
    if transition.expires_at is None or transition.expires_at > at:
        raise SubscriptionTransitionError(
            "La date d’expiration de cette Transition n’est pas atteinte."
        )
    return _set_transition_status(
        transition,
        SubscriptionTransitionStatus.EXPIRED,
        at=at,
    )


@transaction.atomic
def fail_subscription_transition(*, transition, failure_code, reason=""):
    transition = SubscriptionTransition.objects.select_for_update().get(pk=transition.pk)
    if transition.status == SubscriptionTransitionStatus.FAILED:
        return transition
    if transition.status not in OPEN_TRANSITION_STATUSES:
        raise SubscriptionTransitionError(
            "Cette Transition ne peut plus être marquée failed."
        )
    return _set_transition_status(
        transition,
        SubscriptionTransitionStatus.FAILED,
        reason=reason,
        failure_code=failure_code,
    )
