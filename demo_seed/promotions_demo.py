from __future__ import annotations

from datetime import timedelta

from promotions.models import DiscountType, Promotion, PromotionCode, PromotionRedemption, RedemptionStatus
from tickets.models import TicketOrderStatus

from .common import SeedContext, backdate, money, upsert


def _seed_promotions(ctx: SeedContext) -> None:
    ctx.promotions.clear()
    redemption_orders = [o for o in ctx.orders if o.status in {TicketOrderStatus.CONFIRMED, TicketOrderStatus.CANCELLED, TicketOrderStatus.EXPIRED}]
    used_redemption_orders = set()
    for i, org in enumerate(ctx.organizations[:7]):
        org_events = [e for e in ctx.events if e.organization_id == org.id]
        if not org_events:
            continue
        event = org_events[-1]
        owner = org.memberships.filter(role="owner", is_active=True).first().user
        event_currency = event.ticket_types.first().currency
        fixed_value = money("5.00") if event_currency == "USD" else money("5000")
        promos = [
            ("Bienvenue communauté", DiscountType.PERCENT, money("15.00"), "", True),
            ("Pass ambassadeur", DiscountType.FIXED, fixed_value, event_currency, i % 3 != 0),
        ]
        for j, (name, kind, value, currency, active) in enumerate(promos):
            promo = upsert(Promotion, f"org-{i}-promo-{j}", defaults={
                "organization": org,
                "event": event if j == 1 else None,
                "name": f"{name} {2026 if j == 0 else event.start_at.year}",
                "description": "Offre réaliste de démonstration Makolo avec quotas, fenêtre et suivi de redemption.",
                "discount_type": kind,
                "discount_value": value,
                "max_discount_amount": money("20.00") if kind == DiscountType.PERCENT and i % 2 == 0 else None,
                "min_order_amount": money("10.00") if currency == "USD" else money("0"),
                "currency": currency,
                "starts_at": event.registration_start_at if event else None,
                "ends_at": event.registration_end_at if event else None,
                "max_redemptions": 150 + i * 20,
                "max_redemptions_per_customer": 2,
                "is_active": active,
                "created_by": owner,
            })
            backdate(promo, created_at=max(ctx.as_of - timedelta(days=400), event.start_at - timedelta(days=110)), updated_at=min(ctx.as_of, event.start_at - timedelta(days=20)))
            ctx.promotions.append(promo)
            eligible = list(event.ticket_types.filter(is_public=True)[:2])
            if eligible:
                promo.eligible_ticket_types.set(eligible)

            code = upsert(PromotionCode, f"org-{i}-promo-{j}-code", defaults={
                "promotion": promo,
                "code": f"DEMO{i+1}{'WELCOME' if j == 0 else 'VIP'}",
                "label": "Code public" if j == 0 else "Code partenaires",
                "crm_campaign": None,
                "starts_at": promo.starts_at,
                "ends_at": promo.ends_at,
                "max_redemptions": 80 + i * 5,
                "is_private": j == 1,
                "is_active": active,
                "created_by": owner,
            })
            backdate(code, created_at=promo.created_at + timedelta(days=1), updated_at=promo.updated_at)

            matching_orders = [o for o in redemption_orders if o.event.organization_id == org.id and o.id not in used_redemption_orders]
            if matching_orders:
                order = matching_orders[0]
                used_redemption_orders.add(order.id)
                discount = money("5.00") if order.currency == "USD" else money("5000")
                final = order.total_amount
                subtotal = final + discount
                status = {
                    TicketOrderStatus.CONFIRMED: RedemptionStatus.CONFIRMED,
                    TicketOrderStatus.CANCELLED: RedemptionStatus.REVERSED,
                    TicketOrderStatus.EXPIRED: RedemptionStatus.REVERSED,
                }[order.status]
                redemption = upsert(PromotionRedemption, f"promo-redemption-{i}-{j}", defaults={
                    "promotion": promo,
                    "code": code,
                    "order": order,
                    "buyer": order.buyer,
                    "customer_email": order.customer_email,
                    "status": status,
                    "subtotal_amount": subtotal,
                    "eligible_amount": subtotal,
                    "discount_amount": discount,
                    "final_amount": final,
                    "currency": order.currency,
                    "confirmed_at": order.confirmed_at if status == RedemptionStatus.CONFIRMED else None,
                    "reversed_at": (order.cancelled_at or order.expires_at) if status == RedemptionStatus.REVERSED else None,
                })
                backdate(redemption, reserved_at=order.created_at + timedelta(minutes=1))
