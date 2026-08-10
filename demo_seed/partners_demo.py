from __future__ import annotations

from datetime import timedelta

from partners.models import (
    AffiliateCampaign,
    AttributionStatus,
    CampaignStatus,
    CommissionStatus,
    CommissionType,
    Partner,
    PartnerCommission,
    PartnerKind,
    PartnerPayout,
    PartnerStatus,
    PayoutStatus,
    ReferralAttribution,
    ReferralCode,
    ReferralVisit,
)
from tickets.models import TicketOrderStatus

from .common import SeedContext, backdate, choose, money, stable_uuid, upsert

PARTNER_KINDS = [
    PartnerKind.AMBASSADOR, PartnerKind.INFLUENCER, PartnerKind.AGENCY,
    PartnerKind.MEDIA, PartnerKind.COMMUNITY, PartnerKind.BUSINESS, PartnerKind.OTHER,
]


def _seed_partners(ctx: SeedContext) -> None:
    ctx.affiliate_campaigns.clear()
    used_orders = set()
    for org_index, org in enumerate(ctx.organizations[:7]):
        owner = org.memberships.filter(role="owner", is_active=True).first().user
        org_events = [e for e in ctx.events if e.organization_id == org.id]
        if not org_events:
            continue

        partners = []
        for j in range(6):
            user = ctx.users[(org_index * 17 + j + 25) % len(ctx.users)] if j < 4 else None
            partner = upsert(Partner, f"org-{org_index}-partner-{j}", defaults={
                "organization": org,
                "user": user,
                "kind": PARTNER_KINDS[(org_index+j) % len(PARTNER_KINDS)],
                "status": choose([PartnerStatus.ACTIVE, PartnerStatus.ACTIVE, PartnerStatus.PAUSED, PartnerStatus.INVITED, PartnerStatus.CLOSED], j),
                "name": user.full_name if user else f"{choose(['Radio Copper', 'Campus Connect', 'Creative House', 'Business Network'], org_index+j)} {org_index+1}",
                "email": user.email if user else f"partner{org_index+1}{j+1}@makolo.test",
                "phone": user.phone if user else f"+243 99 770 {org_index}{j}0",
                "public_label": f"Ambassadeur {org.city}" if j == 0 else "",
                "notes": "Partenaire de démonstration pour mesurer acquisition, ventes et commissions.",
                "created_by": owner,
            })
            backdate(partner, created_at=ctx.as_of - timedelta(days=420-org_index*20-j*7), updated_at=ctx.as_of - timedelta(days=20+j))
            partners.append(partner)

        event = org_events[-1]
        campaign_specs = [
            ("Ambassadeurs lancement", CampaignStatus.ACTIVE, CommissionType.PERCENTAGE, money("10.00")),
            ("Réseau partenaires historique", CampaignStatus.ENDED, CommissionType.FIXED, money("2.50") if event.ticket_types.first().currency == "USD" else money("5000")),
        ]
        for cidx, (name, status, ctype, value) in enumerate(campaign_specs):
            campaign_event = event if cidx == 0 else org_events[0]
            currency = campaign_event.ticket_types.first().currency
            campaign = upsert(AffiliateCampaign, f"org-{org_index}-affiliate-{cidx}", defaults={
                "organization": org,
                "event": campaign_event,
                "name": name,
                "status": status,
                "commission_type": ctype,
                "commission_value": value,
                "commission_currency": currency,
                "attribution_window_days": 30,
                "starts_at": campaign_event.registration_start_at,
                "ends_at": campaign_event.registration_end_at,
                "created_by": owner,
            })
            backdate(campaign, created_at=campaign_event.created_at + timedelta(days=10), updated_at=min(ctx.as_of, campaign_event.start_at - timedelta(days=2)))
            ctx.affiliate_campaigns.append(campaign)

            for j, partner in enumerate(partners[:4]):
                code = upsert(ReferralCode, f"org-{org_index}-campaign-{cidx}-partner-{j}", defaults={
                    "campaign": campaign,
                    "partner": partner,
                    "code": f"REF{org_index+1}{cidx+1}{j+1:02d}",
                    "is_active": partner.status == PartnerStatus.ACTIVE,
                    "commission_type_override": CommissionType.PERCENTAGE if j == 3 else "",
                    "commission_value_override": money("15.00") if j == 3 else None,
                })
                backdate(code, created_at=campaign.created_at + timedelta(days=1), updated_at=campaign.updated_at)
                visits = []
                for v in range(7):
                    visit = upsert(ReferralVisit, f"org-{org_index}-campaign-{cidx}-partner-{j}-visit-{v}", defaults={
                        "referral_code": code,
                        "visitor_id": stable_uuid(f"visitor-{org_index}-{cidx}-{j}-{v}"),
                        "landing_path": f"/events/{campaign_event.slug}/",
                        "referrer_domain": choose(["instagram.com", "facebook.com", "wa.me", "youtube.com", ""], v+j),
                    })
                    visited = min(ctx.as_of, campaign_event.start_at - timedelta(days=max(1, 35-v*3)))
                    backdate(visit, created_at=visited)
                    visits.append(visit)

                order = next((o for o in ctx.orders if o.event_id == campaign_event.id and o.id not in used_orders and o.total_amount > 0 and o.status in {TicketOrderStatus.CONFIRMED, TicketOrderStatus.CANCELLED, TicketOrderStatus.EXPIRED}), None)
                if not order:
                    continue
                used_orders.add(order.id)
                attr_status = AttributionStatus.CONFIRMED if order.status == TicketOrderStatus.CONFIRMED else AttributionStatus.REVERSED
                attribution = upsert(ReferralAttribution, f"ref-attribution-{org_index}-{cidx}-{j}", defaults={
                    "order": order,
                    "referral_code": code,
                    "campaign": campaign,
                    "partner": partner,
                    "visitor_id": visits[0].visitor_id,
                    "status": attr_status,
                    "confirmed_at": order.confirmed_at if attr_status == AttributionStatus.CONFIRMED else None,
                    "reversed_at": (order.cancelled_at or order.expires_at) if attr_status == AttributionStatus.REVERSED else None,
                })
                backdate(attribution, attributed_at=order.created_at)

                if attr_status == AttributionStatus.CONFIRMED:
                    commission_amount = ((order.total_amount * code.effective_commission_value / 100).quantize(money("0.01")) if code.effective_commission_type == CommissionType.PERCENTAGE else code.effective_commission_value)
                    comm_status = CommissionStatus.PAID if org_index == 0 and cidx == 0 and j == 0 else choose([CommissionStatus.EARNED, CommissionStatus.PAID, CommissionStatus.EARNED], j+cidx)
                    commission = upsert(PartnerCommission, f"partner-commission-{org_index}-{cidx}-{j}", defaults={
                        "attribution": attribution,
                        "partner": partner,
                        "campaign": campaign,
                        "order": order,
                        "payout": None,
                        "amount": commission_amount,
                        "currency": order.currency,
                        "commission_type": code.effective_commission_type,
                        "commission_value": code.effective_commission_value,
                        "status": comm_status,
                        "earned_at": order.confirmed_at or order.created_at,
                        "reversed_at": None,
                        "paid_at": ctx.as_of - timedelta(days=15+j) if comm_status == CommissionStatus.PAID else None,
                    })
                    backdate(commission, created_at=order.confirmed_at or order.created_at, updated_at=ctx.as_of - timedelta(days=10))

        paid_commissions = list(PartnerCommission.objects.filter(partner__organization=org, status=CommissionStatus.PAID, payout__isnull=True))
        if paid_commissions:
            partner = paid_commissions[0].partner
            currency = paid_commissions[0].currency
            eligible = [c for c in paid_commissions if c.partner_id == partner.id and c.currency == currency]
            amount = sum((c.amount for c in eligible), money("0"))
            payout = upsert(PartnerPayout, f"org-{org_index}-payout", defaults={
                "organization": org,
                "partner": partner,
                "currency": currency,
                "amount": amount,
                "status": PayoutStatus.PAID,
                "reference": f"PAYOUT-DEMO-{org_index+1:03d}",
                "notes": "Paiement partenaire historique de démonstration.",
                "created_by": owner,
                "paid_by": owner,
                "paid_at": ctx.as_of - timedelta(days=12+org_index),
            })
            backdate(payout, created_at=ctx.as_of - timedelta(days=20+org_index), updated_at=ctx.as_of - timedelta(days=12+org_index))
            for commission in eligible:
                commission.payout = payout
                commission.save(update_fields=["payout"])
