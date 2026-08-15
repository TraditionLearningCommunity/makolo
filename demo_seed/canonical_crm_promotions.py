from __future__ import annotations

from decimal import Decimal

from crm.canonical_models import Audience, AudienceMember, AudienceMemberSource, CRMInteraction, CRMInteractionType
from promotions.canonical_models import CommercePromotionRedemption, PromotionOffer, PromotionTargeting
from promotions.models import RedemptionStatus

from .common import SeedContext, upsert


def seed_canonical_crm_promotions(ctx: SeedContext) -> None:
    """Cover 8B models without fabricating historical Domain Events."""
    if not ctx.contacts or not ctx.promotions:
        return

    contact = next((item for item in ctx.contacts if item.user_id), None)
    if contact is not None:
        audience = upsert(
            Audience,
            "canonical-audience-0",
            defaults={
                "organization": contact.organization,
                "name": "Communauté active — démo",
                "description": "Audience statique de démonstration. L’appartenance ne vaut pas consentement marketing.",
                "status": "active",
                "created_by": contact.organization.memberships.filter(role="owner", is_active=True).first().user,
                "source_group": None,
                "source_snapshot": None,
            },
        )
        upsert(
            AudienceMember,
            "canonical-audience-0-member-0",
            defaults={
                "audience": audience,
                "profile": contact.user,
                "source": AudienceMemberSource.MANUAL,
                "source_group": None,
                "source_snapshot": None,
            },
        )
        upsert(
            CRMInteraction,
            "canonical-crm-interaction-0",
            defaults={
                "contact": contact,
                "domain_event": None,
                "interaction_type": CRMInteractionType.LEGACY_EVENT,
                "activity": None,
                "occurred_at": contact.last_seen_at,
            },
        )

        promotion = next(
            (promo for promo in ctx.promotions if promo.organization_id == contact.organization_id),
            ctx.promotions[0],
        )
        activity_id = getattr(promotion.event, "activity_id", None) if promotion.event_id else None
        targeting = PromotionTargeting.objects.filter(promotion=promotion).first()
        if targeting is None:
            targeting = PromotionTargeting.objects.create(
                promotion=promotion,
                activity_id=activity_id,
                audience=audience if promotion.organization_id == audience.organization_id else None,
            )
        else:
            targeting.activity_id = targeting.activity_id or activity_id
            if promotion.organization_id == audience.organization_id:
                targeting.audience = audience
            targeting.save(update_fields=["activity", "audience", "updated_at"])

        ticket_type = promotion.eligible_ticket_types.exclude(offer_id__isnull=True).first()
        if ticket_type is not None:
            target = PromotionOffer.objects.filter(promotion=promotion, offer=ticket_type.offer).first()
            if target is None:
                PromotionOffer.objects.create(
                    promotion=promotion,
                    offer=ticket_type.offer,
                    source="ticket_type",
                )
            elif target.source != "ticket_type":
                target.source = "ticket_type"
                target.save(update_fields=["source"])

    redemption_order = next(
        (
            order
            for order in ctx.orders
            if getattr(order, "commerce_order_id", None)
            and order.buyer_id
            and any(promo.organization_id == order.event.organization_id for promo in ctx.promotions)
        ),
        None,
    )
    if redemption_order is None:
        return
    promotion = next(promo for promo in ctx.promotions if promo.organization_id == redemption_order.event.organization_id)
    code = promotion.codes.first()
    if code is None:
        return
    commerce_order = redemption_order.commerce_order
    discount = Decimal("1.00") if commerce_order.total >= Decimal("1.00") else Decimal("0.00")
    subtotal = commerce_order.total + discount
    existing = CommercePromotionRedemption.objects.filter(commerce_order=commerce_order).first()
    defaults = {
        "promotion": promotion,
        "code": code,
        "commerce_order": commerce_order,
        "buyer": redemption_order.buyer,
        "customer_email": redemption_order.customer_email,
        "status": RedemptionStatus.CONFIRMED if commerce_order.status == "confirmed" else RedemptionStatus.RESERVED,
        "subtotal_amount": subtotal,
        "eligible_amount": subtotal,
        "discount_amount": discount,
        "final_amount": commerce_order.total,
        "currency": commerce_order.currency,
        "confirmed_at": commerce_order.confirmed_at,
        "reversed_at": None,
    }
    if existing is None:
        upsert(
            CommercePromotionRedemption,
            "canonical-commerce-redemption-0",
            defaults=defaults,
        )
    else:
        for field, value in defaults.items():
            setattr(existing, field, value)
        existing.save()
