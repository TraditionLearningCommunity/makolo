from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Count, Sum
from django.utils import timezone

from crm.models import (
    CampaignAttribution,
    CampaignAttributionStatus,
    CampaignRecipient,
    CampaignRecipientStatus,
    CommunicationCampaign,
)
from loyalty.models import (
    LoyaltyAccount,
    LoyaltyProgram,
    LoyaltyRewardRedemption,
    MembershipStatus,
    MembershipSubscription,
)
from organizations.models import OrganizationFollow
from partners.models import (
    AttributionStatus,
    CommissionStatus,
    PartnerCommission,
    ReferralAttribution,
    ReferralVisit,
)
from payments.models import Payment, PaymentStatus, Refund, RefundStatus
from promotions.models import PromotionRedemption, RedemptionStatus
from tickets.models import TicketOrder, TicketOrderStatus

from .models import GrowthChannel, GrowthSpend
from .permissions import user_can_view_growth_financials
from .selectors import get_growth_organizations


ZERO = Decimal("0.00")
SUCCESS_PAYMENT_STATUSES = [PaymentStatus.SUCCEEDED, PaymentStatus.REFUNDED]


def _percent(numerator, denominator):
    if not denominator:
        return None
    return round((numerator / denominator) * 100, 1)


def _identity(*, buyer_id=None, email=""):
    if buyer_id:
        return ("user", str(buyer_id))
    normalized = (email or "").strip().lower()
    return ("email", normalized) if normalized else None


def _month_tuple(value):
    if hasattr(value, "date"):
        value = timezone.localtime(value).date() if timezone.is_aware(value) else value.date()
    return value.year, value.month


def _month_key(value):
    year, month = _month_tuple(value)
    return f"{year:04d}-{month:02d}"


def _month_label(key):
    year, month = [int(item) for item in key.split("-")]
    labels = [
        "Jan", "Fév", "Mar", "Avr", "Mai", "Juin",
        "Juil", "Aoû", "Sep", "Oct", "Nov", "Déc",
    ]
    return f"{labels[month - 1]} {year}"


def _month_offset(first_key, current_key):
    first_year, first_month = [int(item) for item in first_key.split("-")]
    year, month = [int(item) for item in current_key.split("-")]
    return (year - first_year) * 12 + month - first_month


def _previous_months(count):
    today = timezone.localdate()
    year, month = today.year, today.month
    values = []
    for _ in range(count):
        values.append(f"{year:04d}-{month:02d}")
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    return list(reversed(values))


def _confirmed_order_rows(organization):
    return list(
        TicketOrder.objects.filter(
            event__organization=organization,
            status=TicketOrderStatus.CONFIRMED,
        )
        .values(
            "id",
            "event_id",
            "buyer_id",
            "customer_email",
            "currency",
            "total_amount",
            "confirmed_at",
            "created_at",
        )
        .order_by("confirmed_at", "created_at", "id")
    )


def _customer_history(order_rows):
    histories = defaultdict(list)
    for row in order_rows:
        identity = _identity(buyer_id=row["buyer_id"], email=row["customer_email"])
        if not identity:
            continue
        occurred_at = row["confirmed_at"] or row["created_at"]
        histories[identity].append((occurred_at, row))
    for values in histories.values():
        values.sort(key=lambda item: item[0])
    return histories


def _build_customer_metrics(histories):
    now = timezone.now()
    cutoff = now - timedelta(days=30)
    total_customers = len(histories)
    repeat_customers = sum(len(rows) >= 2 for rows in histories.values())
    new_customers_30d = sum(rows[0][0] >= cutoff for rows in histories.values())
    total_orders = sum(len(rows) for rows in histories.values())
    return {
        "customers": total_customers,
        "repeat_customers": repeat_customers,
        "repeat_buyer_percent": _percent(repeat_customers, total_customers),
        "new_customers_30d": new_customers_30d,
        "confirmed_orders": total_orders,
        "orders_per_customer": round(total_orders / total_customers, 2) if total_customers else 0,
    }


def _build_growth_series(histories, months):
    month_keys = _previous_months(months)
    counters = {
        key: {"new_customers": 0, "repeat_orders": 0, "orders": 0}
        for key in month_keys
    }
    for rows in histories.values():
        for index, (occurred_at, _row) in enumerate(rows):
            key = _month_key(occurred_at)
            if key not in counters:
                continue
            counters[key]["orders"] += 1
            if index == 0:
                counters[key]["new_customers"] += 1
            else:
                counters[key]["repeat_orders"] += 1
    return [
        {
            "month": key,
            "label": _month_label(key),
            **counters[key],
        }
        for key in month_keys
    ]


def _build_cohorts(histories, cohort_months):
    by_cohort = defaultdict(list)
    for identity, rows in histories.items():
        purchase_months = {_month_key(occurred_at) for occurred_at, _row in rows}
        first_month = _month_key(rows[0][0])
        by_cohort[first_month].append((identity, purchase_months))

    cohorts = []
    for cohort_key in sorted(by_cohort.keys(), reverse=True)[:12]:
        members = by_cohort[cohort_key]
        cells = []
        for offset in range(cohort_months):
            active = 0
            for _identity_key, purchase_months in members:
                if any(
                    _month_offset(cohort_key, purchase_month) == offset
                    for purchase_month in purchase_months
                ):
                    active += 1
            cells.append(
                {
                    "offset": offset,
                    "active_customers": active,
                    "retention_percent": _percent(active, len(members)),
                }
            )
        cohorts.append(
            {
                "cohort": cohort_key,
                "label": _month_label(cohort_key),
                "size": len(members),
                "months": cells,
            }
        )
    return cohorts


def _build_follower_metrics(organization, histories):
    follows = list(
        OrganizationFollow.objects.filter(organization=organization).values(
            "user_id", "followed_at"
        )
    )
    converted = 0
    repeat_followers = 0
    for follow in follows:
        rows = histories.get(("user", str(follow["user_id"])), [])
        post_follow_orders = [row for row in rows if row[0] >= follow["followed_at"]]
        if post_follow_orders:
            converted += 1
        if len(post_follow_orders) >= 2:
            repeat_followers += 1
    return {
        "followers": len(follows),
        "followers_converted": converted,
        "follower_to_buyer_percent": _percent(converted, len(follows)),
        "followers_with_repeat_purchase": repeat_followers,
    }


def _build_loyalty_metrics(organization, histories):
    program = LoyaltyProgram.objects.filter(organization=organization).first()
    if not program:
        return {
            "enabled": False,
            "accounts": 0,
            "active_memberships": 0,
            "reward_redemptions": 0,
            "points_debt_accounts": 0,
            "loyalty_repeat_buyer_percent": None,
            "non_loyalty_repeat_buyer_percent": None,
            "repeat_rate_lift_points": None,
        }

    now = timezone.now()
    account_user_ids = set(
        LoyaltyAccount.objects.filter(program=program).values_list("user_id", flat=True)
    )
    loyalty_histories = {
        identity: rows
        for identity, rows in histories.items()
        if identity[0] == "user" and identity[1] in {str(item) for item in account_user_ids}
    }
    non_loyalty_histories = {
        identity: rows for identity, rows in histories.items() if identity not in loyalty_histories
    }
    loyalty_repeat = sum(len(rows) >= 2 for rows in loyalty_histories.values())
    non_loyalty_repeat = sum(len(rows) >= 2 for rows in non_loyalty_histories.values())
    loyalty_rate = _percent(loyalty_repeat, len(loyalty_histories))
    non_loyalty_rate = _percent(non_loyalty_repeat, len(non_loyalty_histories))
    lift = None
    if loyalty_rate is not None and non_loyalty_rate is not None:
        lift = round(loyalty_rate - non_loyalty_rate, 1)

    return {
        "enabled": program.is_active,
        "program_id": str(program.pk),
        "program_name": program.name,
        "accounts": len(account_user_ids),
        "active_memberships": MembershipSubscription.objects.filter(
            program=program,
            status=MembershipStatus.ACTIVE,
            starts_at__lte=now,
            ends_at__gt=now,
        ).count(),
        "reward_redemptions": LoyaltyRewardRedemption.objects.filter(
            reward__program=program,
            status="redeemed",
        ).count(),
        "points_debt_accounts": LoyaltyAccount.objects.filter(
            program=program,
            points_balance__lt=0,
        ).count(),
        "loyalty_repeat_buyer_percent": loyalty_rate,
        "non_loyalty_repeat_buyer_percent": non_loyalty_rate,
        "repeat_rate_lift_points": lift,
    }


def _payment_ltv(organization):
    customer_money = defaultdict(lambda: defaultdict(lambda: {"gross": ZERO, "refunds": ZERO}))
    payments = Payment.objects.filter(
        order__event__organization=organization,
        status__in=SUCCESS_PAYMENT_STATUSES,
    ).values(
        "id",
        "order__buyer_id",
        "order__customer_email",
        "currency",
        "amount",
    )
    payment_identity = {}
    for row in payments:
        identity = _identity(
            buyer_id=row["order__buyer_id"],
            email=row["order__customer_email"],
        )
        if not identity:
            continue
        currency = (row["currency"] or "").upper()
        payment_identity[row["id"]] = (identity, currency)
        customer_money[identity][currency]["gross"] += row["amount"] or ZERO

    refunds = Refund.objects.filter(
        payment__order__event__organization=organization,
        status=RefundStatus.SUCCEEDED,
    ).values(
        "payment_id",
        "payment__order__buyer_id",
        "payment__order__customer_email",
        "currency",
        "amount",
    )
    for row in refunds:
        identity = _identity(
            buyer_id=row["payment__order__buyer_id"],
            email=row["payment__order__customer_email"],
        )
        if not identity:
            continue
        currency = (row["currency"] or "").upper()
        customer_money[identity][currency]["refunds"] += row["amount"] or ZERO

    currencies = sorted(
        {
            currency
            for values in customer_money.values()
            for currency in values.keys()
            if currency
        }
    )
    result = []
    for currency in currencies:
        rows = [values[currency] for values in customer_money.values() if currency in values]
        gross = sum((row["gross"] for row in rows), ZERO)
        refunds_total = sum((row["refunds"] for row in rows), ZERO)
        net = gross - refunds_total
        result.append(
            {
                "currency": currency,
                "customers": len(rows),
                "gross": gross,
                "refunds": refunds_total,
                "net": net,
                "average_net_ltv": (net / len(rows)).quantize(Decimal("0.01")) if rows else ZERO,
            }
        )
    return result


def _sum_spends(spends):
    totals = defaultdict(lambda: ZERO)
    for spend in spends:
        totals[spend.currency] += spend.amount
    return totals


def _money_rows(revenue, intrinsic_cost, configured_spend):
    currencies = sorted(set(revenue) | set(intrinsic_cost) | set(configured_spend))
    result = []
    for currency in currencies:
        revenue_amount = revenue.get(currency, ZERO)
        intrinsic = intrinsic_cost.get(currency, ZERO)
        configured = configured_spend.get(currency, ZERO)
        total_cost = intrinsic + configured
        contribution = revenue_amount - total_cost
        roi = None
        if total_cost > 0:
            roi = round(float((contribution / total_cost) * 100), 1)
        result.append(
            {
                "currency": currency,
                "attributed_revenue": revenue_amount,
                "intrinsic_cost": intrinsic,
                "configured_spend": configured,
                "total_cost": total_cost,
                "contribution": contribution,
                "contribution_roi_percent": roi,
            }
        )
    return result


def _crm_channel(organization, spends, *, source_limit):
    campaigns = list(
        CommunicationCampaign.objects.filter(organization=organization)
        .annotate(
            recipient_count=Count("recipients", distinct=True),
            attribution_count=Count(
                "attributions",
                filter=models_q_campaign_confirmed(),
                distinct=True,
            ),
        )
        .order_by("-created_at")
    )
    recipient_rows = CampaignRecipient.objects.filter(campaign__organization=organization).values(
        "campaign_id", "status", "click_count"
    )
    sent_by_campaign = defaultdict(int)
    clicks_by_campaign = defaultdict(int)
    for row in recipient_rows:
        if row["status"] == CampaignRecipientStatus.SENT:
            sent_by_campaign[row["campaign_id"]] += 1
        clicks_by_campaign[row["campaign_id"]] += row["click_count"] or 0

    conversions_by_campaign = defaultdict(int)
    revenue_by_campaign = defaultdict(lambda: defaultdict(lambda: ZERO))
    for row in CampaignAttribution.objects.filter(
        campaign__organization=organization,
        status=CampaignAttributionStatus.CONFIRMED,
    ).values("campaign_id", "currency", "revenue_amount"):
        conversions_by_campaign[row["campaign_id"]] += 1
        revenue_by_campaign[row["campaign_id"]][row["currency"]] += row["revenue_amount"] or ZERO

    spend_by_campaign = defaultdict(list)
    for spend in spends:
        if spend.channel == GrowthChannel.CRM and spend.crm_campaign_id:
            spend_by_campaign[spend.crm_campaign_id].append(spend)

    sources = []
    channel_revenue = defaultdict(lambda: ZERO)
    for campaign in campaigns:
        for currency, value in revenue_by_campaign[campaign.pk].items():
            channel_revenue[currency] += value
        sources.append(
            {
                "id": str(campaign.pk),
                "name": campaign.name,
                "sent": sent_by_campaign[campaign.pk],
                "clicks": clicks_by_campaign[campaign.pk],
                "conversions": conversions_by_campaign[campaign.pk],
                "click_percent": _percent(clicks_by_campaign[campaign.pk], sent_by_campaign[campaign.pk]),
                "conversion_percent": _percent(conversions_by_campaign[campaign.pk], sent_by_campaign[campaign.pk]),
                "money": _money_rows(
                    revenue_by_campaign[campaign.pk],
                    {},
                    _sum_spends(spend_by_campaign[campaign.pk]),
                ),
            }
        )
    sources.sort(key=lambda row: (row["conversions"], row["clicks"]), reverse=True)
    channel_spend = _sum_spends([spend for spend in spends if spend.channel == GrowthChannel.CRM])
    return {
        "campaigns": len(campaigns),
        "sent": sum(sent_by_campaign.values()),
        "clicks": sum(clicks_by_campaign.values()),
        "conversions": sum(conversions_by_campaign.values()),
        "conversion_percent": _percent(sum(conversions_by_campaign.values()), sum(sent_by_campaign.values())),
        "money": _money_rows(channel_revenue, {}, channel_spend),
        "sources": sources[:source_limit],
    }


def models_q_campaign_confirmed():
    # Kept as a small helper so the import list above remains explicit and the
    # annotation does not duplicate the status literal.
    from django.db.models import Q

    return Q(attributions__status=CampaignAttributionStatus.CONFIRMED)


def _partners_channel(organization, spends, *, source_limit):
    visits = ReferralVisit.objects.filter(referral_code__campaign__organization=organization).count()
    attributions = ReferralAttribution.objects.filter(
        campaign__organization=organization,
        status=AttributionStatus.CONFIRMED,
    ).select_related("campaign", "order")
    conversions = attributions.count()
    revenue = defaultdict(lambda: ZERO)
    conversion_by_campaign = defaultdict(int)
    revenue_by_campaign = defaultdict(lambda: defaultdict(lambda: ZERO))
    for attribution in attributions:
        currency = attribution.order.currency
        amount = attribution.order.total_amount or ZERO
        revenue[currency] += amount
        conversion_by_campaign[attribution.campaign_id] += 1
        revenue_by_campaign[attribution.campaign_id][currency] += amount

    intrinsic_cost = defaultdict(lambda: ZERO)
    commission_by_campaign = defaultdict(lambda: defaultdict(lambda: ZERO))
    for row in PartnerCommission.objects.filter(
        campaign__organization=organization,
        status__in=[CommissionStatus.EARNED, CommissionStatus.PAID],
    ).values("campaign_id", "currency", "amount"):
        intrinsic_cost[row["currency"]] += row["amount"] or ZERO
        commission_by_campaign[row["campaign_id"]][row["currency"]] += row["amount"] or ZERO

    campaign_names = {
        row["id"]: row["name"]
        for row in organization.affiliate_campaigns.values("id", "name")
    }
    spend_by_campaign = defaultdict(list)
    for spend in spends:
        if spend.channel == GrowthChannel.PARTNERS and spend.partner_campaign_id:
            spend_by_campaign[spend.partner_campaign_id].append(spend)
    sources = []
    for campaign_id, name in campaign_names.items():
        sources.append(
            {
                "id": str(campaign_id),
                "name": name,
                "conversions": conversion_by_campaign[campaign_id],
                "money": _money_rows(
                    revenue_by_campaign[campaign_id],
                    commission_by_campaign[campaign_id],
                    _sum_spends(spend_by_campaign[campaign_id]),
                ),
            }
        )
    sources.sort(key=lambda row: row["conversions"], reverse=True)
    channel_spend = _sum_spends([spend for spend in spends if spend.channel == GrowthChannel.PARTNERS])
    return {
        "visits": visits,
        "conversions": conversions,
        "visit_to_buyer_percent": _percent(conversions, visits),
        "money": _money_rows(revenue, intrinsic_cost, channel_spend),
        "sources": sources[:source_limit],
    }


def _promotions_channel(organization, spends, *, source_limit):
    redemptions = PromotionRedemption.objects.filter(
        promotion__organization=organization,
        status=RedemptionStatus.CONFIRMED,
    ).select_related("promotion")
    revenue = defaultdict(lambda: ZERO)
    discount = defaultdict(lambda: ZERO)
    by_promotion = defaultdict(lambda: {"count": 0, "revenue": defaultdict(lambda: ZERO), "discount": defaultdict(lambda: ZERO)})
    for redemption in redemptions:
        revenue[redemption.currency] += redemption.final_amount or ZERO
        discount[redemption.currency] += redemption.discount_amount or ZERO
        bucket = by_promotion[redemption.promotion_id]
        bucket["count"] += 1
        bucket["revenue"][redemption.currency] += redemption.final_amount or ZERO
        bucket["discount"][redemption.currency] += redemption.discount_amount or ZERO

    spend_by_promotion = defaultdict(list)
    for spend in spends:
        if spend.channel == GrowthChannel.PROMOTIONS and spend.promotion_id:
            spend_by_promotion[spend.promotion_id].append(spend)
    promotion_names = {
        row["id"]: row["name"]
        for row in organization.promotions.values("id", "name")
    }
    sources = []
    for promotion_id, bucket in by_promotion.items():
        sources.append(
            {
                "id": str(promotion_id),
                "name": promotion_names.get(promotion_id, "Promotion"),
                "redemptions": bucket["count"],
                "money": _money_rows(
                    bucket["revenue"],
                    bucket["discount"],
                    _sum_spends(spend_by_promotion[promotion_id]),
                ),
            }
        )
    sources.sort(key=lambda row: row["redemptions"], reverse=True)
    channel_spend = _sum_spends([spend for spend in spends if spend.channel == GrowthChannel.PROMOTIONS])
    return {
        "redemptions": redemptions.count(),
        "money": _money_rows(revenue, discount, channel_spend),
        "sources": sources[:source_limit],
    }


def _loyalty_channel(organization, spends, loyalty_metrics):
    program = LoyaltyProgram.objects.filter(organization=organization).first()
    revenue = defaultdict(lambda: ZERO)
    discount = defaultdict(lambda: ZERO)
    reward_order_count = 0
    if program:
        reward_redemptions = PromotionRedemption.objects.filter(
            promotion__organization=organization,
            status=RedemptionStatus.CONFIRMED,
            code__loyalty_reward_redemptions__reward__program=program,
            code__loyalty_reward_redemptions__status="redeemed",
        ).distinct()
        reward_order_count = reward_redemptions.count()
        for redemption in reward_redemptions:
            revenue[redemption.currency] += redemption.final_amount or ZERO
            discount[redemption.currency] += redemption.discount_amount or ZERO
    channel_spend = _sum_spends([spend for spend in spends if spend.channel == GrowthChannel.LOYALTY])
    return {
        **loyalty_metrics,
        "reward_driven_orders": reward_order_count,
        "money": _money_rows(revenue, discount, channel_spend),
    }


def _build_insights(payload):
    metrics = payload["customer_metrics"]
    follower = payload["followers"]
    loyalty = payload["channels"]["loyalty"]
    crm = payload["channels"]["crm"]
    partners = payload["channels"]["partners"]
    insights = []

    if metrics["customers"] >= 10 and (metrics["repeat_buyer_percent"] or 0) < 20:
        insights.append(
            {
                "level": "warning",
                "title": "Répétition d'achat faible",
                "body": f"{metrics['repeat_buyer_percent'] or 0}% des acheteurs confirmés ont acheté au moins deux fois.",
                "action": "Travaillez le post-événement, la fidélité et les prochaines éditions avant d'augmenter uniquement l'acquisition.",
            }
        )
    if follower["followers"] >= 10 and (follower["follower_to_buyer_percent"] or 0) < 10:
        insights.append(
            {
                "level": "info",
                "title": "Audience sociale peu convertie",
                "body": f"{follower['follower_to_buyer_percent'] or 0}% des followers ont acheté après leur follow.",
                "action": "Comparez les CTA, offres et événements proposés aux followers sans assimiler follow et consentement marketing.",
            }
        )
    if crm["sent"] >= 10 and (crm["conversion_percent"] or 0) < 3:
        insights.append(
            {
                "level": "warning",
                "title": "Conversion CRM à surveiller",
                "body": f"{crm['conversion_percent'] or 0}% des destinataires envoyés sont reliés à une conversion confirmée.",
                "action": "Comparez segments, messages et attribution plutôt que le volume d'envoi seul.",
            }
        )
    if partners["visits"] >= 20 and (partners["visit_to_buyer_percent"] or 0) < 2:
        insights.append(
            {
                "level": "warning",
                "title": "Trafic partenaire peu converti",
                "body": f"{partners['visit_to_buyer_percent'] or 0}% des visites partenaires deviennent une commande confirmée attribuée.",
                "action": "Revoyez la qualité des audiences partenaires, la landing page et l'offre de l'événement.",
            }
        )
    lift = loyalty.get("repeat_rate_lift_points")
    if lift is not None and loyalty.get("accounts", 0) >= 5:
        insights.append(
            {
                "level": "positive" if lift > 0 else "info",
                "title": "Écart de répétition fidélité",
                "body": f"Les membres fidélité présentent un écart de {lift:+.1f} point(s) de répétition par rapport aux autres acheteurs.",
                "action": "Interprétez cet écart comme une corrélation, pas comme une causalité automatique du programme fidélité.",
            }
        )

    if payload["financial_visible"]:
        negative = []
        for channel_name, channel in payload["channels"].items():
            for money in channel.get("money", []):
                roi = money.get("contribution_roi_percent")
                if roi is not None and roi < 0:
                    negative.append((channel_name, money["currency"], roi))
        if negative:
            name, currency, roi = sorted(negative, key=lambda item: item[2])[0]
            insights.append(
                {
                    "level": "critical",
                    "title": "Contribution Growth négative",
                    "body": f"Le canal {name} affiche {roi}% sur les coûts observables en {currency}.",
                    "action": "Vérifiez le coût saisi, les commissions/remises et la fenêtre d'attribution avant de modifier le budget.",
                }
            )
    return insights[:6]


def build_organization_growth(organization, user, *, months=12, cohort_months=6, source_limit=8):
    months = min(max(int(months or 12), 3), 24)
    cohort_months = min(max(int(cohort_months or 6), 3), 12)
    source_limit = min(max(int(source_limit or 8), 3), 20)

    order_rows = _confirmed_order_rows(organization)
    histories = _customer_history(order_rows)
    customer_metrics = _build_customer_metrics(histories)
    follower_metrics = _build_follower_metrics(organization, histories)
    loyalty_metrics = _build_loyalty_metrics(organization, histories)
    financial_visible = user_can_view_growth_financials(user, organization)
    spends = list(
        GrowthSpend.objects.filter(organization=organization).select_related(
            "crm_campaign", "partner_campaign", "promotion", "loyalty_program"
        )
    ) if financial_visible else []

    crm = _crm_channel(organization, spends, source_limit=source_limit)
    partners = _partners_channel(organization, spends, source_limit=source_limit)
    promotions = _promotions_channel(organization, spends, source_limit=source_limit)
    loyalty = _loyalty_channel(organization, spends, loyalty_metrics)

    if not financial_visible:
        for channel in [crm, partners, promotions, loyalty]:
            channel["money"] = []
            for source in channel.get("sources", []):
                source["money"] = []

    payload = {
        "organization": {
            "id": str(organization.pk),
            "slug": organization.slug,
            "name": organization.name,
        },
        "customer_metrics": customer_metrics,
        "followers": follower_metrics,
        "growth_series": _build_growth_series(histories, months),
        "cohorts": _build_cohorts(histories, cohort_months),
        "channels": {
            "crm": crm,
            "partners": partners,
            "promotions": promotions,
            "loyalty": loyalty,
        },
        "financial_visible": financial_visible,
        "ltv_by_currency": _payment_ltv(organization) if financial_visible else [],
        "spend_entries": [
            {
                "id": str(spend.pk),
                "channel": spend.channel,
                "channel_label": spend.get_channel_display(),
                "label": spend.label,
                "amount": spend.amount,
                "currency": spend.currency,
                "incurred_at": spend.incurred_at,
                "source": spend.source_label,
            }
            for spend in spends[:30]
        ],
        "methodology": {
            "repeat_buyer": "Acheteur avec au moins deux commandes confirmées dans l'organisation.",
            "follower_conversion": "Follower ayant une commande confirmée après la date de follow.",
            "ltv": "Paiements réussis moins remboursements réussis, calculés séparément par devise et client identifié.",
            "roi": "Ratio de contribution sur revenus attribués et coûts observables uniquement; il ne prouve pas une causalité incrémentale ni une marge comptable complète.",
        },
        "generated_at": timezone.now(),
    }
    payload["insights"] = _build_insights(payload)
    return payload


def build_growth_portfolio(user):
    organizations = list(get_growth_organizations(user)[:30])
    cards = []
    for organization in organizations:
        order_rows = _confirmed_order_rows(organization)
        histories = _customer_history(order_rows)
        customer_metrics = _build_customer_metrics(histories)
        follower_metrics = _build_follower_metrics(organization, histories)
        cards.append(
            {
                "organization": organization,
                "customers": customer_metrics["customers"],
                "repeat_customers": customer_metrics["repeat_customers"],
                "repeat_buyer_percent": customer_metrics["repeat_buyer_percent"],
                "new_customers_30d": customer_metrics["new_customers_30d"],
                "followers": follower_metrics["followers"],
                "follower_to_buyer_percent": follower_metrics["follower_to_buyer_percent"],
                "financial_visible": user_can_view_growth_financials(user, organization),
            }
        )
    return {
        "organizations_count": len(cards),
        "customers": sum(card["customers"] for card in cards),
        "repeat_customers": sum(card["repeat_customers"] for card in cards),
        "new_customers_30d": sum(card["new_customers_30d"] for card in cards),
        "cards": cards,
        "generated_at": timezone.now(),
    }
