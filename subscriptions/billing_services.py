from __future__ import annotations

from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from payments.models import (
    PaymentObligationProcessingMode,
    PaymentObligationReason,
    PaymentObligationStatus,
)
from payments.obligation_services import create_payment_obligation

from .billing_models import PlanVersionBillingTerms, SubscriptionBillingObligation
from .contracts import PlanVersionStatus, SubscriptionTransitionStatus
from .runtime_models import Subscription
from .transition_models import OPEN_TRANSITION_STATUSES, SubscriptionTransition


SETTLED_BILLING_STATUSES = {
    PaymentObligationStatus.SATISFIED,
    PaymentObligationStatus.WAIVED,
}


class SubscriptionBillingError(ValidationError):
    pass


def _actor_or_none(actor):
    return actor if getattr(actor, "is_authenticated", False) else None


def _source_key(*, subscription, billing_terms, billing_key):
    return f"subscription:{subscription.pk}:billing:{billing_terms.pk}:{billing_key}"[:180]


def _resolve_due_at(*, billing_terms, at=None):
    at = at or timezone.now()
    return at + timedelta(days=billing_terms.payment_due_days)


def transition_billing_is_settled(transition):
    links = list(
        SubscriptionBillingObligation.objects.filter(transition=transition)
        .select_related("obligation")
        .order_by("created_at", "id")
    )
    if not links:
        return True
    return all(link.obligation.status in SETTLED_BILLING_STATUSES for link in links)


@transaction.atomic
def create_subscription_billing_obligation(
    *,
    subscription,
    billing_terms,
    billing_key,
    transition=None,
    actor=None,
    due_at=None,
):
    key = (billing_key or "").strip()
    if not key:
        raise SubscriptionBillingError("Une provenance de billing explicite est obligatoire.")

    subscription = (
        Subscription.objects.select_for_update(of=("self",))
        .select_related("profile", "space")
        .get(pk=subscription.pk)
    )
    billing_terms = (
        PlanVersionBillingTerms.objects.select_for_update()
        .select_related("plan_version__plan")
        .get(pk=billing_terms.pk)
    )
    if billing_terms.plan_version.status == PlanVersionStatus.DRAFT:
        raise SubscriptionBillingError("Une obligation ne peut pas utiliser des Billing Terms draft.")
    if billing_terms.plan_version.plan.subject_type != subscription.subject_type:
        raise SubscriptionBillingError("Les Billing Terms ne correspondent pas au sujet de la Subscription.")

    locked_transition = None
    if transition is not None:
        locked_transition = (
            SubscriptionTransition.objects.select_for_update(of=("self",))
            .select_related("subscription", "target_plan_version")
            .get(pk=transition.pk)
        )
        if locked_transition.subscription_id != subscription.pk:
            raise SubscriptionBillingError("La Transition doit appartenir à la même Subscription.")
        if locked_transition.target_plan_version_id != billing_terms.plan_version_id:
            raise SubscriptionBillingError("Le billing d’une Transition doit utiliser les termes de sa cible pinnée.")
        if locked_transition.status not in OPEN_TRANSITION_STATUSES:
            existing = SubscriptionBillingObligation.objects.filter(
                subscription=subscription,
                billing_terms=billing_terms,
                billing_key=key,
            ).select_related("obligation").first()
            if existing:
                return existing.obligation
            raise SubscriptionBillingError("La Transition n’accepte plus de nouvelle obligation de billing.")

    if billing_terms.amount == 0:
        return None

    existing_link = SubscriptionBillingObligation.objects.filter(
        subscription=subscription,
        billing_terms=billing_terms,
        billing_key=key,
    ).select_related("obligation").first()
    if existing_link:
        if locked_transition is not None and existing_link.transition_id != locked_transition.pk:
            raise SubscriptionBillingError("Cette provenance de billing appartient à une autre Transition.")
        return existing_link.obligation

    payer_profile = subscription.profile if subscription.profile_id else None
    payer_space = subscription.space if subscription.space_id else None
    obligation = create_payment_obligation(
        journey=None,
        commerce_order=None,
        step=None,
        reason=PaymentObligationReason.SUBSCRIPTION,
        label=f"Subscription {billing_terms.plan_version.plan.code} v{billing_terms.plan_version.version}",
        amount=billing_terms.amount,
        currency=billing_terms.currency,
        processing_mode=PaymentObligationProcessingMode.MAKOLO_PROVIDER,
        payer_profile=payer_profile,
        payer_space=payer_space,
        payee_platform=True,
        due_at=due_at or _resolve_due_at(billing_terms=billing_terms),
        created_by=_actor_or_none(actor),
        source_key=_source_key(
            subscription=subscription,
            billing_terms=billing_terms,
            billing_key=key,
        ),
    )
    link = SubscriptionBillingObligation(
        subscription=subscription,
        transition=locked_transition,
        billing_terms=billing_terms,
        obligation=obligation,
        billing_key=key,
    )
    try:
        link.save()
    except IntegrityError as exc:
        concurrent = SubscriptionBillingObligation.objects.filter(
            subscription=subscription,
            billing_terms=billing_terms,
            billing_key=key,
        ).select_related("obligation").first()
        if concurrent:
            return concurrent.obligation
        raise SubscriptionBillingError("Impossible de lier cette obligation Subscription de façon unique.") from exc
    return obligation


@transaction.atomic
def ensure_transition_billing_obligation(*, transition, actor=None):
    transition = (
        SubscriptionTransition.objects.select_for_update(of=("self",))
        .select_related("subscription__profile", "subscription__space", "target_plan_version")
        .get(pk=transition.pk)
    )
    try:
        billing_terms = transition.target_plan_version.billing_terms
    except PlanVersionBillingTerms.DoesNotExist:
        return None
    return create_subscription_billing_obligation(
        subscription=transition.subscription,
        billing_terms=billing_terms,
        transition=transition,
        billing_key=f"transition:{transition.pk}",
        actor=actor,
    )


@transaction.atomic
def sync_subscription_billing_obligation(*, obligation):
    link = (
        SubscriptionBillingObligation.objects.select_for_update()
        .filter(obligation=obligation)
        .select_related("transition")
        .first()
    )
    if not link or not link.transition_id:
        return None
    from .transition_services import evaluate_transition_readiness

    return evaluate_transition_readiness(transition=link.transition)
