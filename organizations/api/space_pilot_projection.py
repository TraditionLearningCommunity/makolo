from __future__ import annotations

from analytics_app.services import build_portfolio_analytics
from authorization.constants import PermissionCode
from authorization.selectors import has_direct_space_permission

from .workspace_projection import build_space_workspace


def _metric(key, value, *, unit="count", period=None):
    return {
        "key": key,
        "state": "known",
        "value": value,
        "unit": unit,
        "period": period,
    }


def build_space_pilot_projection(*, profile, space):
    workspace = build_space_workspace(profile, space)
    if workspace is None:
        return None

    direct_space = workspace["authority"]["scope"] == "space"
    analytics_visible = direct_space and has_direct_space_permission(
        profile, space, PermissionCode.ANALYTICS_VIEW
    )
    sections = {}

    if analytics_visible:
        analytics = build_portfolio_analytics(profile, organization=space)
        state = "known" if analytics["events_count"] else "insufficient_data"
        metrics = [
            _metric("events_count", analytics["events_count"]),
            _metric("published_count", analytics["published_count"]),
            _metric("upcoming_count", analytics["upcoming_count"]),
            _metric("active_tickets", analytics["active_tickets"]),
            _metric("used_tickets", analytics["used_tickets"]),
            _metric("confirmed_orders", analytics["confirmed_orders"]),
            _metric("waitlist_waiting", analytics["waitlist_waiting"]),
        ]
        if analytics["attendance_percent"] is None:
            metrics.append(
                {
                    "key": "attendance_percent",
                    "state": "insufficient_data",
                    "value": None,
                    "unit": "percent",
                    "period": None,
                }
            )
        else:
            metrics.append(
                _metric(
                    "attendance_percent",
                    analytics["attendance_percent"],
                    unit="percent",
                )
            )

        money = []
        for row in analytics["money_totals"]:
            money.append(
                {
                    "key": f'money:{row["currency"]}',
                    "state": "known",
                    "currency": row["currency"],
                    "gross": str(row["gross"]),
                    "refunds": str(row["refunds"]),
                    "net": str(row["net"]),
                    "period": None,
                }
            )

        sections["analytics"] = {
            "state": state,
            "metrics": metrics,
            "money": money,
            "signals": [],
            "source": {"kind": "analytics", "id": str(space.pk)},
            "generated_at": analytics["generated_at"],
            "links": {
                "deep": f"/api/v1/analytics/overview/?organization={space.slug}"
            },
        }

    return {
        "authority": workspace["authority"],
        "sections": sections,
        "signals": [],
        "links": {"workspace": workspace["links"]["workspace"]},
        "capabilities": {
            "view_analytics": analytics_visible,
            "view_financials": analytics_visible
            and has_direct_space_permission(
                profile, space, PermissionCode.ANALYTICS_FINANCIALS_VIEW
            ),
        },
    }
