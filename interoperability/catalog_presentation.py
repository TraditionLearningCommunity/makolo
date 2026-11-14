"""Presentation-only catalogue and N3 selection for owner-scoped Connections.

All offers come from the owner catalogue and all connection rows are already
filtered by the caller's authority. No provider IDs, keys or URLs are invented.
"""
from __future__ import annotations

from interoperability.presentation import capability_label


def connection_experience_context(request, *, offers, connections):
    rows = [
        {
            **offer,
            "capability_labels": [
                capability_label(code)
                for code in offer.get("capabilities", ())
            ],
        }
        for offer in offers
    ]
    query = request.GET.get("q", "").strip()[:80]
    category = request.GET.get("cap", "").strip()[:80]
    capabilities = sorted(
        {
            capability
            for offer in rows
            for capability in offer.get("capabilities", ())
        }
    )
    if category not in capabilities:
        category = ""

    visible = [
        offer for offer in rows
        if (
            not query
            or query.casefold() in " ".join(
                [
                    offer.get("label", ""),
                    offer.get("description", ""),
                    *offer["capability_labels"],
                ]
            ).casefold()
        )
        and (not category or category in offer.get("capabilities", ()))
    ]

    return {
        "visible_connection_offers": visible,
        "capability_options": [
            {"code": code, "label": capability_label(code)}
            for code in capabilities
        ],
        "catalog_query": query,
        "catalog_category": category,
        "connections_tab": (
            "mine" if request.GET.get("tab") == "mine" else "discover"
        ),
        "selected_connection_offer": next(
            (
                offer for offer in rows
                if offer.get("code") == request.GET.get("offer")
            ),
            None,
        ),
        "selected_personal_connection": next(
            (
                connection for connection in connections
                if str(connection.get("id")) == request.GET.get("connection")
            ),
            None,
        ),
    }
