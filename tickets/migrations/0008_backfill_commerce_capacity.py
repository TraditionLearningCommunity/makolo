from decimal import Decimal

from django.db import migrations


def backfill_commerce_capacity(apps, schema_editor):
    Event = apps.get_model("events", "Event")
    Occurrence = apps.get_model("activities", "Occurrence")
    CapacityPool = apps.get_model("capacity", "CapacityPool")
    CapacityReservation = apps.get_model("capacity", "CapacityReservation")
    Offer = apps.get_model("commerce", "Offer")
    CommerceOrder = apps.get_model("commerce", "CommerceOrder")
    CommerceOrderItem = apps.get_model("commerce", "CommerceOrderItem")
    TicketType = apps.get_model("tickets", "TicketType")
    TicketOrder = apps.get_model("tickets", "TicketOrder")
    TicketOrderItem = apps.get_model("tickets", "TicketOrderItem")

    event_scope = {}
    for event in Event.objects.all().only("pk", "activity_id").iterator():
        occurrence_id = None
        if event.activity_id:
            occurrence_id = (
                Occurrence.objects.filter(activity_id=event.activity_id)
                .order_by("start_at", "pk")
                .values_list("pk", flat=True)
                .first()
            )
        event_scope[event.pk] = (event.activity_id, occurrence_id)

    for ticket_type in TicketType.objects.all().order_by("pk").iterator():
        activity_id, occurrence_id = event_scope.get(ticket_type.event_id, (None, None))
        if not activity_id:
            continue
        pool, _ = CapacityPool.objects.update_or_create(
            source_key=f"ticket-type:{ticket_type.pk}",
            defaults={
                "activity_id": activity_id,
                "occurrence_id": occurrence_id,
                "label": ticket_type.name,
                "total_quantity": ticket_type.quantity_total,
                "is_active": ticket_type.is_active,
            },
        )
        offer, _ = Offer.objects.update_or_create(
            source_key=f"ticket-type:{ticket_type.pk}",
            defaults={
                "activity_id": activity_id,
                "occurrence_id": occurrence_id,
                "capacity_pool_id": pool.pk,
                "name": ticket_type.name,
                "description": ticket_type.description,
                "unit_price": ticket_type.price,
                "currency": ticket_type.currency,
                "payment_mode": "none" if ticket_type.price == 0 else "upfront",
                "available_from": ticket_type.sales_start_at,
                "available_until": ticket_type.sales_end_at,
                "min_quantity": ticket_type.min_per_order,
                "max_quantity": ticket_type.max_per_order,
                "status": "active" if ticket_type.is_active else "inactive",
            },
        )
        TicketType.objects.filter(pk=ticket_type.pk).update(offer_id=offer.pk, capacity_pool_id=pool.pk)

    order_status_map = {
        "pending": "pending",
        "confirmed": "confirmed",
        "cancelled": "cancelled",
        "expired": "expired",
    }
    reservation_status_map = {
        "pending": "held",
        "confirmed": "committed",
        "cancelled": "released",
        "expired": "expired",
    }

    for order in TicketOrder.objects.all().order_by("created_at", "pk").iterator():
        if not order.journey_id:
            continue
        activity_id, _ = event_scope.get(order.event_id, (None, None))
        if not activity_id:
            continue
        payee_space_id = apps.get_model("activities", "Activity").objects.filter(pk=activity_id).values_list("space_id", flat=True).first()
        legacy_items = list(TicketOrderItem.objects.filter(order_id=order.pk).order_by("created_at", "pk"))
        subtotal = sum((item.unit_price * item.quantity for item in legacy_items), Decimal("0.00"))
        if subtotal < order.total_amount:
            subtotal = order.total_amount
        discount_total = subtotal - order.total_amount
        commerce_order, _ = CommerceOrder.objects.update_or_create(
            source_key=f"ticket-order:{order.pk}",
            defaults={
                "journey_id": order.journey_id,
                "buyer_id": order.buyer_id,
                "payee_space_id": payee_space_id,
                "status": order_status_map.get(order.status, "pending"),
                "currency": order.currency,
                "payment_mode": "none" if order.total_amount == 0 else "upfront",
                "subtotal": subtotal,
                "discount_total": discount_total,
                "total": order.total_amount,
                "expires_at": order.expires_at,
                "confirmed_at": order.confirmed_at,
                "cancelled_at": order.cancelled_at,
            },
        )
        TicketOrder.objects.filter(pk=order.pk).update(commerce_order_id=commerce_order.pk)

        remaining_discount = discount_total
        for item in legacy_items:
            offer_id = TicketType.objects.filter(pk=item.ticket_type_id).values_list("offer_id", flat=True).first()
            pool_id = TicketType.objects.filter(pk=item.ticket_type_id).values_list("capacity_pool_id", flat=True).first()
            if not offer_id or not pool_id:
                continue
            reservation, _ = CapacityReservation.objects.update_or_create(
                pool_id=pool_id,
                journey_id=order.journey_id,
                source_key=f"ticket-item:{item.pk}",
                defaults={
                    "quantity": item.quantity,
                    "status": reservation_status_map.get(order.status, "held"),
                    "expires_at": order.expires_at if order.status == "pending" else None,
                    "committed_at": order.confirmed_at if order.status == "confirmed" else None,
                    "released_at": order.cancelled_at if order.status == "cancelled" else None,
                    "expired_at": order.expires_at if order.status == "expired" else None,
                },
            )
            line_subtotal = item.unit_price * item.quantity
            line_discount = min(line_subtotal, remaining_discount)
            remaining_discount -= line_discount
            commerce_item, _ = CommerceOrderItem.objects.update_or_create(
                order_id=commerce_order.pk,
                offer_id=offer_id,
                defaults={
                    "beneficiary_id": order.buyer_id,
                    "capacity_reservation_id": reservation.pk,
                    "quantity": item.quantity,
                    "label_snapshot": TicketType.objects.filter(pk=item.ticket_type_id).values_list("name", flat=True).first() or "Tarif",
                    "unit_price": item.unit_price,
                    "line_subtotal": line_subtotal,
                    "discount_total": line_discount,
                    "line_total": line_subtotal - line_discount,
                },
            )
            TicketOrderItem.objects.filter(pk=item.pk).update(commerce_item_id=commerce_item.pk)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("tickets", "0007_commerce_capacity_bridges"),
    ]
    operations = [migrations.RunPython(backfill_commerce_capacity, noop)]
