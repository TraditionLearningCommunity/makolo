from collections import defaultdict
from decimal import Decimal

from django.db.models import Count, Sum

from .models import (
    AttributionStatus,
    CommissionStatus,
    PartnerCommission,
    ReferralAttribution,
    ReferralVisit,
)


def _percent(numerator, denominator):
    if not denominator:
        return None
    return round((numerator / denominator) * 100, 1)


def build_event_partner_analytics(event, *, finance_visible=False):
    """Return acquisition aggregates for one event without buyer PII."""
    visits_qs = ReferralVisit.objects.filter(referral_code__campaign__event=event)
    attributions_qs = ReferralAttribution.objects.filter(campaign__event=event)

    visits = visits_qs.count()
    attributed_orders = attributions_qs.count()
    confirmed_orders = attributions_qs.filter(status=AttributionStatus.CONFIRMED).count()
    reversed_orders = attributions_qs.filter(status=AttributionStatus.REVERSED).count()

    visits_by_partner = defaultdict(int)
    for row in (
        visits_qs.values("referral_code__partner_id")
        .annotate(total=Count("id"))
    ):
        visits_by_partner[row["referral_code__partner_id"]] = row["total"]

    attributed_by_partner = defaultdict(int)
    confirmed_by_partner = defaultdict(int)
    partner_names = {}
    for row in (
        attributions_qs.values(
            "partner_id",
            "partner__name",
            "partner__public_label",
        )
        .annotate(total=Count("id"))
    ):
        partner_id = row["partner_id"]
        attributed_by_partner[partner_id] = row["total"]
        partner_names[partner_id] = row["partner__public_label"] or row["partner__name"]
    for row in (
        attributions_qs.filter(status=AttributionStatus.CONFIRMED)
        .values("partner_id")
        .annotate(total=Count("id"))
    ):
        confirmed_by_partner[row["partner_id"]] = row["total"]

    partner_ids = set(visits_by_partner) | set(attributed_by_partner)
    if partner_ids - set(partner_names):
        from .models import Partner

        for row in Partner.objects.filter(pk__in=partner_ids).values("id", "name", "public_label"):
            partner_names[row["id"]] = row["public_label"] or row["name"]

    leaderboard = []
    for partner_id in partner_ids:
        partner_visits = visits_by_partner[partner_id]
        partner_attributed = attributed_by_partner[partner_id]
        partner_confirmed = confirmed_by_partner[partner_id]
        leaderboard.append(
            {
                "partner_id": str(partner_id),
                "name": partner_names.get(partner_id, "Partenaire"),
                "visits": partner_visits,
                "attributed_orders": partner_attributed,
                "confirmed_orders": partner_confirmed,
                "conversion_percent": _percent(partner_confirmed, partner_visits),
            }
        )
    leaderboard.sort(key=lambda item: (item["confirmed_orders"], item["visits"]), reverse=True)

    commission_totals = []
    if finance_visible:
        rows = (
            PartnerCommission.objects.filter(campaign__event=event)
            .values("currency", "status")
            .annotate(total=Sum("amount"))
            .order_by("currency", "status")
        )
        grouped = defaultdict(lambda: {
            CommissionStatus.EARNED: Decimal("0"),
            CommissionStatus.PAID: Decimal("0"),
            CommissionStatus.REVERSED: Decimal("0"),
        })
        for row in rows:
            grouped[row["currency"]][row["status"]] = row["total"] or Decimal("0")
        commission_totals = [
            {
                "currency": currency,
                "earned": totals[CommissionStatus.EARNED],
                "paid": totals[CommissionStatus.PAID],
                "reversed": totals[CommissionStatus.REVERSED],
            }
            for currency, totals in sorted(grouped.items())
        ]

    insights = []
    conversion = _percent(confirmed_orders, visits)
    if visits >= 20 and conversion is not None and conversion < 3:
        insights.append(
            {
                "level": "warning",
                "title": "Trafic partenaire peu converti",
                "body": f"{visits} visites partenaires n’ont produit que {confirmed_orders} commande(s) confirmée(s), soit {conversion}%.",
                "action": "Comparez les messages, audiences et offres des ambassadeurs avant d’augmenter leur diffusion.",
            }
        )
    if leaderboard and leaderboard[0]["confirmed_orders"] >= 3:
        leader = leaderboard[0]
        insights.append(
            {
                "level": "positive",
                "title": "Canal partenaire performant",
                "body": f"{leader['name']} a déjà généré {leader['confirmed_orders']} commande(s) confirmée(s).",
                "action": "Envisagez un objectif ou une campagne dédiée sans modifier rétroactivement les commissions acquises.",
            }
        )

    return {
        "visits": visits,
        "attributed_orders": attributed_orders,
        "confirmed_orders": confirmed_orders,
        "reversed_orders": reversed_orders,
        "conversion_percent": conversion,
        "leaderboard": leaderboard[:10],
        "commission_totals": commission_totals,
        "financial_visible": finance_visible,
        "insights": insights,
    }
