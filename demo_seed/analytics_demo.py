from __future__ import annotations

from datetime import timedelta

from analytics_app.domain_event_consumer import ANALYTICS_EVENT_TYPES, consume_analytics_event
from analytics_app.models import AnalyticsFact, GrowthChannel, GrowthSpend
from core.models import DomainEventOutbox

from .common import SeedContext, backdate, money, upsert


def _seed_growth_spend(ctx: SeedContext) -> None:
    for org_index, org in enumerate(ctx.organizations[:6]):
        owner = org.memberships.filter(role="owner", is_active=True).first().user
        event = next((e for e in reversed(ctx.events) if e.organization_id == org.id), None)
        crm_campaign = next((c for c in ctx.crm_campaigns if c.organization_id == org.id), None)
        partner_campaign = next((c for c in ctx.affiliate_campaigns if c.organization_id == org.id), None)
        promotion = next((p for p in ctx.promotions if p.organization_id == org.id), None)
        loyalty = next((p for p in ctx.loyalty_programs if p.organization_id == org.id), None)
        specs = [
            (GrowthChannel.CRM, "Production campagne CRM", money("35"), crm_campaign, None, None, None),
            (GrowthChannel.PARTNERS, "Budget ambassadeurs", money("80"), None, partner_campaign, None, None),
            (GrowthChannel.PROMOTIONS, "Coût offre acquisition", money("45"), None, None, promotion, None),
            (GrowthChannel.LOYALTY, "Animation programme fidélité", money("60"), None, None, None, loyalty),
            (GrowthChannel.OTHER, "Impression affiches & terrain", money("50"), None, None, None, None),
        ]
        for j, (channel, label, amount, crm, partner, promo, loyal) in enumerate(specs):
            if channel != GrowthChannel.OTHER and not any([crm, partner, promo, loyal]):
                continue
            spend = upsert(GrowthSpend, f"org-{org_index}-growth-spend-{j}", defaults={
                "organization": org,
                "event": event,
                "channel": channel,
                "crm_campaign": crm,
                "partner_campaign": partner,
                "promotion": promo,
                "loyalty_program": loyal,
                "label": label,
                "amount": amount + money(org_index * 5),
                "currency": "USD",
                "incurred_at": (ctx.as_of - timedelta(days=30+j*8+org_index)).date(),
                "notes": "Dépense historique réaliste de démonstration.",
                "created_by": owner,
            })
            backdate(spend, created_at=ctx.as_of - timedelta(days=28+j*8+org_index), updated_at=ctx.as_of - timedelta(days=10))


def _seed_analytics_fact(ctx: SeedContext) -> None:
    """Project one already-existing canonical event for realistic model coverage.

    The seed never fabricates an old outbox row and calls no notification or
    automation consumer. It only materializes Analytics' own idempotent view.
    """
    if AnalyticsFact.objects.exists():
        return
    domain_event = (
        DomainEventOutbox.objects.filter(event_type__in=ANALYTICS_EVENT_TYPES)
        .order_by("occurred_at", "id")
        .first()
    )
    if domain_event is not None:
        consume_analytics_event(domain_event)
        ctx.add("analytics_facts", AnalyticsFact.objects.count())
