"""Bounded read-only owner views for L5, not parallel business entities.

Capacity comes from Capacity selectors; offers/orders from Commerce;
payment aggregates from Payment; locations from Geography via OccurrencePlace.
Sensitive person and credential details are never returned in this summary.
"""
from django.db.models import Count, Q, Sum

from authorization.constants import PermissionCode
from authorization.services import can
from capacity.selectors import capacity_availability_many, pools_for_activity
from commerce.selectors import applicable_offers, orders_for_activity
from operations.permissions import user_can_view_activity_operations


def _authorized(actor, occurrence, activity_permission, space_permission=None):
    if can(
        actor, activity_permission, activity=occurrence.activity,
        include_platform=False,
    ):
        return True
    return bool(
        space_permission and occurrence.activity.space_id
        and can(
            actor, space_permission, occurrence.activity.space,
            include_platform=False,
        )
    )


def available_insights(*, occurrence, viewer, organizer_scope=True):
    """Only advertise capabilities whose real read owner can be called."""
    if not organizer_scope:
        return []
    result = []
    rules = (
        ("capacity", "Capacité", PermissionCode.ACTIVITY_CAPACITY_VIEW, None),
        ("commerce", "Commerce", PermissionCode.ACTIVITY_COMMERCE_VIEW, None),
        ("finance", "Finances", PermissionCode.ACTIVITY_FINANCE_VIEW, PermissionCode.FINANCE_VIEW),
        ("places", "Lieux", PermissionCode.SPACE_PLACES_VIEW, PermissionCode.SPACE_PLACES_VIEW),
    )
    for key, label, permission, space_permission in rules:
        if key == "places" and not occurrence.activity.space_id:
            continue
        if _authorized(viewer, occurrence, permission, space_permission):
            result.append({
                "kind": key,
                "label": label,
                "territory": "organizer",
                "source": {
                    "capacity": "capacity.selectors",
                    "commerce": "commerce.selectors",
                    "finance": "payments.models",
                    "places": "geography",
                }[key],
                "read_path": (
                    f"/api/v1/operations/occurrences/{occurrence.pk}/experience/insights/{key}/"
                ),
            })
    return result


def resolve_occurrence_insight(*, occurrence, viewer, kind, organizer_scope=True):
    available = {
        row["kind"]: row
        for row in available_insights(
            occurrence=occurrence, viewer=viewer,
            organizer_scope=organizer_scope,
        )
    }
    if kind not in available:
        return None

    if kind == "capacity":
        # Activity-wide pools without another occurrence are applicable too.
        pools = [
            pool for pool in pools_for_activity(occurrence.activity)
            if pool.occurrence_id in {None, occurrence.pk} and pool.is_active
        ]
        availability = capacity_availability_many(pools)
        entries = []
        for pool in pools:
            current = availability[pool.pk]
            entries.append({
                "id": str(pool.pk),
                "label": pool.label,
                "scope": "occurrence" if pool.occurrence_id else "activity",
                "total": current.total,
                "held": current.held,
                "committed": current.committed,
                "available": current.available,
                "unlimited": current.unlimited,
            })
        return {"kind": kind, "source": "capacity.selectors", "entries": entries}

    if kind == "commerce":
        # No buyer, price secret, payment identifier or mutable order metadata.
        offers = list(applicable_offers(occurrence=occurrence))
        orders = list(
            orders_for_activity(occurrence.activity)
            .filter(journey__occurrence=occurrence)
            .values("status").annotate(count=Count("pk")).order_by("status")
        )
        return {
            "kind": kind,
            "source": "commerce.selectors",
            "offers": [
                {
                    "id": str(offer.pk), "name": offer.name,
                    "status": offer.status, "currency": offer.currency,
                    "unit_price": str(offer.unit_price),
                }
                for offer in offers
            ],
            "order_counts": orders,
        }

    if kind == "finance":
        from payments.models import Payment, PaymentObligation

        obligations = list(
            PaymentObligation.objects.filter(
                Q(journey__occurrence=occurrence)
                | Q(commerce_order__journey__occurrence=occurrence),
                Q(journey__activity=occurrence.activity)
                | Q(commerce_order__journey__activity=occurrence.activity),
            ).values("currency", "status")
            .annotate(count=Count("pk"), amount=Sum("amount"))
            .order_by("currency", "status")
        )
        payments = list(
            Payment.objects.filter(
                Q(obligation__journey__occurrence=occurrence)
                | Q(commerce_order__journey__occurrence=occurrence),
            ).values("currency", "status")
            .annotate(count=Count("pk"), amount=Sum("amount"))
            .order_by("currency", "status")
        )
        return {
            "kind": kind, "source": "payments.models",
            "obligations": [
                {**row, "amount": str(row["amount"] or 0)}
                for row in obligations
            ],
            "payments": [
                {**row, "amount": str(row["amount"] or 0)}
                for row in payments
            ],
        }

    if kind == "places":
        return {
            "kind": kind, "source": "geography",
            "entries": [
                {
                    "id": str(link.place_id), "role": link.role,
                    "name": link.place.name,
                    "locality": link.place.locality,
                    "address_line": link.place.address_line,
                }
                for link in occurrence.place_links.select_related("place").all()
            ],
        }
    return None
