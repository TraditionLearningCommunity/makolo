from __future__ import annotations

from django.urls import reverse

from partners.selectors import (
    get_commissions_visible_to,
    get_partners_visible_to,
    get_payouts_visible_to,
    get_referral_codes_visible_to,
)
from partners.services import build_partner_metrics, partner_balance


PARTNER_DETAIL_LIMIT = 50


def _code_payload(code):
    return {
        "id": str(code.pk),
        "code": code.code,
        "state": "usable" if code.is_usable else "unavailable",
        "is_usable": bool(code.is_usable),
        "campaign": {
            "id": str(code.campaign_id),
            "name": code.campaign.name,
            "state": code.campaign.status,
            "event": {
                "id": str(code.campaign.event_id),
                "title": code.campaign.event.title,
            },
        },
        "links": {
            "referral": f"/partners/r/{code.code}/",
        },
        "capabilities": ["view_code"] if code.is_active else [],
    }


def _commission_payload(commission):
    return {
        "id": str(commission.pk),
        "amount": commission.amount,
        "currency": commission.currency,
        "state": commission.status,
        "earned_at": commission.earned_at,
        "reversed_at": commission.reversed_at,
        "paid_at": commission.paid_at,
        "campaign": {
            "id": str(commission.campaign_id),
            "name": commission.campaign.name,
            "event": {
                "id": str(commission.campaign.event_id),
                "title": commission.campaign.event.title,
            },
        },
        "payout_id": str(commission.payout_id) if commission.payout_id else None,
    }


def _payout_payload(payout):
    return {
        "id": str(payout.pk),
        "amount": payout.amount,
        "currency": payout.currency,
        "state": payout.status,
        "created_at": payout.created_at,
        "paid_at": payout.paid_at,
    }


def build_personal_partner_detail_data(profile, *, partner_id):
    relationship = (
        get_partners_visible_to(profile)
        .filter(pk=partner_id, user=profile)
        .select_related("organization")
        .first()
    )
    if relationship is None:
        return None

    codes = list(
        get_referral_codes_visible_to(profile)
        .filter(partner=relationship)
        .select_related("campaign__event", "campaign__organization")
        .order_by("-is_active", "campaign__name", "code", "id")[:PARTNER_DETAIL_LIMIT]
    )
    commissions = list(
        get_commissions_visible_to(profile)
        .filter(partner=relationship)
        .select_related("campaign__event", "payout")
        .order_by("-earned_at", "id")[:PARTNER_DETAIL_LIMIT]
    )
    payouts = list(
        get_payouts_visible_to(profile)
        .filter(partner=relationship)
        .order_by("-created_at", "id")[:PARTNER_DETAIL_LIMIT]
    )
    metrics = build_partner_metrics(relationship, finance_visible=True)

    return {
        "kind": "partner_relationship",
        "id": str(relationship.pk),
        "relationship": {
            "state": relationship.status,
            "kind": relationship.kind,
            "kind_label": relationship.get_kind_display(),
            "display_name": relationship.display_name,
            "organization": {
                "kind": "space",
                "id": str(relationship.organization_id),
                "name": relationship.organization.name,
                "slug": relationship.organization.slug,
            },
            "authority": {
                "space_authority_granted": False,
                "source": "partner_relationship",
            },
        },
        "codes": {
            "items": [_code_payload(code) for code in codes],
            "count": len(codes),
        },
        "economic_state": {
            "unallocated_earned": partner_balance(relationship),
            "commissions": metrics.get("commissions", []),
            "aggregate_across_currencies": None,
        },
        "commissions": {
            "items": [_commission_payload(commission) for commission in commissions],
            "count": len(commissions),
        },
        "payouts": {
            "items": [_payout_payload(payout) for payout in payouts],
            "count": len(payouts),
        },
        "metrics": {
            "visits": metrics["visits"],
            "attributed_orders": metrics["attributed_orders"],
            "confirmed_orders": metrics["confirmed_orders"],
            "conversion_percent": metrics["conversion_percent"],
            "active_codes": metrics["active_codes"],
        },
        "capabilities": (
            ["view", "view_code"]
            if any(code.is_active for code in codes)
            else ["view"]
        ),
        "links": {
            "self": reverse(
                "personal-projections:partner-detail",
                kwargs={"pk": relationship.pk},
            ),
            "collection": reverse("personal-projections:partners"),
        },
    }
