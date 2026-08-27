"""T30 product contract for Growth Analytics.

The historical implementation still computes follower-derived figures for
backward compatibility inside its private Python payload. T30 deliberately
removes those fields before any web/API product surface can consume them:
Follow is an action relationship, not a commercial value or popularity metric.
"""

from .growth import (
    build_growth_portfolio as _build_growth_portfolio_legacy,
    build_organization_growth as _build_organization_growth_legacy,
)


def build_growth_portfolio(user):
    payload = _build_growth_portfolio_legacy(user)
    for card in payload.get("cards", []):
        card.pop("followers", None)
        card.pop("follower_to_buyer_percent", None)
    return payload


def build_organization_growth(organization, user, *, months=12, cohort_months=6, source_limit=8):
    payload = _build_organization_growth_legacy(
        organization,
        user,
        months=months,
        cohort_months=cohort_months,
        source_limit=source_limit,
    )
    payload.pop("followers", None)
    methodology = payload.get("methodology") or {}
    methodology.pop("follower_conversion", None)
    payload["insights"] = [
        insight
        for insight in payload.get("insights", [])
        if insight.get("title") != "Audience sociale peu convertie"
    ]
    return payload
