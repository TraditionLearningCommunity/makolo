"""Read-only Subscription billing composition for Web and native clients.

No invoices, prices or payment decisions are created here. Owners remain
Subscription (pinned terms) and Payments (obligations and payment status).
"""
from __future__ import annotations

from dataclasses import replace

from django.db.models import Q

from payments.models import PaymentObligation

from .billing_models import PlanVersionBillingTerms


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


def personal_billing_obligations(subscription, *, offset=0, limit=20):
    """One ordered, deduplicated source of financial obligations for this Profile.

    Commercial billing and acquisition Requirement obligations may both point
    at a PaymentObligation. Filtering by the canonical payer avoids suggesting
    that a Profile can pay another subject's obligation.
    """
    if subscription.profile_id is None:
        raise ValueError("personal_billing_obligations requires a Profile subscription")
    obligations = (
        PaymentObligation.objects.filter(payer_profile_id=subscription.profile_id)
        .filter(
            Q(subscription_billing_link__subscription=subscription)
            | Q(subscription_transition_links__transition__subscription=subscription)
        )
        .distinct()
        .order_by("-created_at", "-pk")
    )
    page = list(obligations[offset : offset + limit + 1])
    rows = [
        {
            "id": str(obligation.pk),
            "label": obligation.label,
            "amount": str(obligation.amount),
            "currency": obligation.currency,
            "status": obligation.status,
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
