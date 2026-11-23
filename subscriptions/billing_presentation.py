"""Read-only Subscription billing composition for Web and native clients.

No invoices, prices or payment decisions are created here. Owners remain
Subscription (pinned terms) and Payments (obligations and payment status).
"""
from __future__ import annotations

from dataclasses import replace

from django.db.models import Q

from authorization.constants import PermissionCode
from authorization.services import space_ids_with_permission

from payments.models import PaymentObligation

from .billing_models import PlanVersionBillingTerms


_OBLIGATION_STATUS_LABELS = {
    "pending": "À régler",
    "processing": "En cours de traitement",
    "satisfied": "Réglée",
    "waived": "Dispensée",
    "expired": "Expirée",
    "cancelled": "Annulée",
    "refunded": "Remboursée",
}


def terms_as_dict(terms):
    if terms is None:
        return None
    return {
        "amount": str(terms.amount),
        "currency": terms.currency,
        "period_unit": terms.billing_period_unit,
        "period_count": terms.billing_period_count,
        "payment_due_days": terms.payment_due_days,
        "grace_period_days": terms.grace_period_days,
    }


def with_billing_terms(product):
    """Enrich the existing product projection, without modifying its owners."""
    entries = [product.current_base, *product.active_addons, *product.catalog]
    identifiers = [row["plan_version_id"] for row in entries if row is not None]
    terms_by_id = {
        str(terms.plan_version_id): terms_as_dict(terms)
        for terms in PlanVersionBillingTerms.objects.filter(plan_version_id__in=identifiers)
    }

    def attach(row):
        return {**row, "billing_terms": terms_by_id.get(row["plan_version_id"])} if row else None

    return replace(
        product,
        current_base=attach(product.current_base),
        active_addons=tuple(attach(row) for row in product.active_addons),
        catalog=tuple(attach(row) for row in product.catalog),
    )


def subscription_billing_obligations(subscription, *, offset=0, limit=20):
    """Payment-owned facts for the exact Subscription subject, no delegation."""
    if subscription.profile_id is not None:
        payer = Q(payer_profile_id=subscription.profile_id, payer_space__isnull=True)
    elif subscription.space_id is not None:
        payer = Q(payer_space_id=subscription.space_id, payer_profile__isnull=True)
    else:
        raise ValueError("Subscription subject is missing")
    obligations = (
        PaymentObligation.objects.filter(payer)
        .filter(
            Q(subscription_billing_link__subscription=subscription)
            | Q(subscription_transition_links__transition__subscription=subscription)
        )
        .select_related("subscription_billing_link__transition",
                        "subscription_billing_link__billing_terms__plan_version")
        .distinct()
        .order_by("-created_at", "-pk")
    )
    page = list(obligations[offset : offset + limit + 1])
    rows = [
        {
            "id": str(obligation.pk),
            "label": (
                "Abonnement — " + obligation.subscription_billing_link.billing_terms.plan_version.name
                if hasattr(obligation, "subscription_billing_link")
                else obligation.label
            ),
            "transition_id": (
                str(obligation.subscription_billing_link.transition_id)
                if hasattr(obligation, "subscription_billing_link")
                and obligation.subscription_billing_link.transition_id
                else None
            ),
            "amount": str(obligation.amount),
            "currency": obligation.currency,
            "status": obligation.status,
            "status_label": _OBLIGATION_STATUS_LABELS.get(obligation.status, "État à vérifier"),
            "processing_mode": obligation.processing_mode,
            "due_at": obligation.due_at,
            "created_at": obligation.created_at,
            "satisfied_at": obligation.satisfied_at,
            "can_start_payment": (
                obligation.processing_mode == "makolo_provider"
                and obligation.status in {"pending", "processing"}
            ),
        }
        for obligation in page[:limit]
    ]
    return {
        "items": rows,
        "next_offset": offset + limit if len(page) > limit else None,
    }


def next_payment_url_for_actor(transition, actor):
    """Use the existing Payments route only if this actor may open the obligation.

    The Subscription manager role alone never grants Space payment access.
    """
    from django.urls import reverse
    from payments.selectors import obligations_visible_to

    if transition.subscription.space_id is not None:
        finance_spaces = space_ids_with_permission(actor, PermissionCode.FINANCE_VIEW)
        if finance_spaces is not None and transition.subscription.space_id not in finance_spaces:
            return None

    link = (
        transition.billing_obligation_links.select_related("obligation")
        .order_by("-created_at", "-pk").first()
    )
    if link is None or link.obligation.status not in {"pending", "processing"}:
        return None
    if not obligations_visible_to(actor).filter(pk=link.obligation_id).exists():
        return None
    return reverse("payments:obligation-start", kwargs={"obligation_pk": link.obligation_id})


def personal_billing_obligations(subscription, *, offset=0, limit=20):
    """Retained personal entrypoint for its Web/native callers."""
    if subscription.profile_id is None:
        raise ValueError("personal_billing_obligations requires a Profile subscription")
    return subscription_billing_obligations(subscription, offset=offset, limit=limit)


def transition_payment_action_for_actor(transition, *, actor):
    """Resolve an open transition's payment action independently of billing pagination.

    Both Subscription billing and legacy Requirement-payment links remain owned
    by their respective domains. This read-only projection cannot grant payment
    access, confirm an obligation or change a transition.
    """
    from payments.selectors import obligations_visible_to

    billing_links = transition.billing_obligation_links.select_related("obligation").all()
    requirement_links = transition.payment_obligation_links.select_related("obligation").all()
    by_id = {
        link.obligation_id: link.obligation
        for link in [*billing_links, *requirement_links]
    }
    obligations = sorted(
        by_id.values(),
        key=lambda obligation: (obligation.created_at, str(obligation.pk)),
        reverse=True,
    )
    released = {"cancelled", "expired", "refunded"}
    can_cancel = all(obligation.status in released for obligation in obligations)
    payable = next(
        (
            obligation for obligation in obligations
            if obligation.status in {"pending", "processing"}
            and obligation.processing_mode == "makolo_provider"
        ),
        None,
    )
    has_unsettled_payment = any(
        obligation.status in {"pending", "processing"} for obligation in obligations
    )
    if payable is None:
        return {
            "can_cancel": can_cancel, "payment": None,
            "payment_access_required": False,
            "has_unsettled_payment": has_unsettled_payment,
        }
    accessible = obligations_visible_to(actor).filter(pk=payable.pk).exists()
    return {
        "can_cancel": can_cancel,
        "payment": (
            {"id": str(payable.pk), "amount": str(payable.amount), "currency": payable.currency}
            if accessible else None
        ),
        "payment_access_required": not accessible,
        "has_unsettled_payment": has_unsettled_payment,
    }
