from decimal import Decimal

from django.db import migrations


def _available_source_key(Model, source_key, *, exclude_pk=None):
    queryset = Model.objects.filter(source_key=source_key)
    if exclude_pk is not None:
        queryset = queryset.exclude(pk=exclude_pk)
    return not queryset.exists()


def _attach_source_key(Model, obj, source_key):
    if getattr(obj, "source_key", None):
        return obj
    if _available_source_key(Model, source_key, exclude_pk=obj.pk):
        Model.objects.filter(pk=obj.pk).update(source_key=source_key)
        obj.source_key = source_key
    return obj


def _reference_for_legacy_order(CommerceOrder, order):
    legacy_reference = (order.reference or "").strip()
    if legacy_reference and not CommerceOrder.objects.filter(reference=legacy_reference).exists():
        return legacy_reference

    token = str(order.pk).replace("-", "").upper()
    base = f"TKT-{token[:20]}"[:24]
    candidate = base
    suffix = 2
    while CommerceOrder.objects.filter(reference=candidate).exists():
        suffix_text = f"-{suffix}"
        candidate = f"{base[: 24 - len(suffix_text)]}{suffix_text}"
        suffix += 1
    return candidate


def _resolve_capacity_pool(CapacityPool, ticket_type, *, activity_id, occurrence_id):
    source_key = f"ticket-type:{ticket_type.pk}"

    if ticket_type.capacity_pool_id:
        linked = CapacityPool.objects.filter(pk=ticket_type.capacity_pool_id).first()
        if linked is not None:
            return _attach_source_key(CapacityPool, linked, source_key)

    existing = CapacityPool.objects.filter(source_key=source_key).first()
    if existing is not None:
        return existing

    return CapacityPool.objects.create(
        activity_id=activity_id,
        occurrence_id=occurrence_id,
        label=ticket_type.name,
        total_quantity=ticket_type.quantity_total,
        is_active=ticket_type.is_active,
        source_key=source_key,
    )


def _resolve_offer(Offer, ticket_type, *, pool, activity_id, occurrence_id):
    source_key = f"ticket-type:{ticket_type.pk}"

    if ticket_type.offer_id:
        linked = Offer.objects.filter(pk=ticket_type.offer_id).first()
        if linked is not None:
            return _attach_source_key(Offer, linked, source_key)

    existing = Offer.objects.filter(source_key=source_key).first()
    if existing is not None:
        return existing

    return Offer.objects.create(
        activity_id=activity_id,
        occurrence_id=occurrence_id,
        capacity_pool_id=pool.pk,
        name=ticket_type.name,
        description=ticket_type.description,
        unit_price=ticket_type.price,
        currency=ticket_type.currency,
        payment_mode="none" if ticket_type.price == 0 else "upfront",
        available_from=ticket_type.sales_start_at,
        available_until=ticket_type.sales_end_at,
        min_quantity=ticket_type.min_per_order,
        max_quantity=ticket_type.max_per_order,
        status="active" if ticket_type.is_active else "inactive",
        source_key=source_key,
    )


def _resolve_commerce_order(CommerceOrder, order, *, defaults):
    source_key = f"ticket-order:{order.pk}"

    if order.commerce_order_id:
        linked = CommerceOrder.objects.filter(pk=order.commerce_order_id).first()
        if linked is not None:
            return _attach_source_key(CommerceOrder, linked, source_key)

    existing = CommerceOrder.objects.filter(source_key=source_key).first()
    if existing is not None:
        return existing

    legacy_reference = (order.reference or "").strip()
    if legacy_reference:
        existing = CommerceOrder.objects.filter(
            reference=legacy_reference,
            journey_id=order.journey_id,
        ).first()
        if existing is not None:
            return _attach_source_key(CommerceOrder, existing, source_key)

    return CommerceOrder.objects.create(
        reference=_reference_for_legacy_order(CommerceOrder, order),
        source_key=source_key,
        **defaults,
    )


def _resolve_reservation(
    CapacityReservation,
    *,
    existing_reservation_id,
    pool_id,
    journey_id,
    source_key,
    defaults,
):
    if existing_reservation_id:
        linked = CapacityReservation.objects.filter(pk=existing_reservation_id).first()
        if linked is not None:
            return linked

    existing = CapacityReservation.objects.filter(
        pool_id=pool_id,
        journey_id=journey_id,
        source_key=source_key,
    ).first()
    if existing is not None:
        return existing

    return CapacityReservation.objects.create(
        pool_id=pool_id,
        journey_id=journey_id,
        source_key=source_key,
        **defaults,
    )


def backfill_commerce_capacity(apps, schema_editor):
    Activity = apps.get_model("activities", "Activity")
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

        pool = _resolve_capacity_pool(
            CapacityPool,
            ticket_type,
            activity_id=activity_id,
            occurrence_id=occurrence_id,
        )
        offer = _resolve_offer(
            Offer,
            ticket_type,
            pool=pool,
            activity_id=activity_id,
            occurrence_id=occurrence_id,
        )
        TicketType.objects.filter(pk=ticket_type.pk).update(
            offer_id=offer.pk,
            capacity_pool_id=pool.pk,
        )

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

        payee_space_id = (
            Activity.objects.filter(pk=activity_id)
            .values_list("space_id", flat=True)
            .first()
        )
        legacy_items = list(
            TicketOrderItem.objects.filter(order_id=order.pk).order_by("created_at", "pk")
        )
        subtotal = sum(
            (item.unit_price * item.quantity for item in legacy_items),
            Decimal("0.00"),
        )
        if subtotal < order.total_amount:
            subtotal = order.total_amount
        discount_total = subtotal - order.total_amount

        commerce_order = _resolve_commerce_order(
            CommerceOrder,
            order,
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
            ticket_type = TicketType.objects.filter(pk=item.ticket_type_id).first()
            if ticket_type is None or not ticket_type.offer_id or not ticket_type.capacity_pool_id:
                continue

            existing_commerce_item = None
            existing_reservation_id = None
            if item.commerce_item_id:
                existing_commerce_item = CommerceOrderItem.objects.filter(pk=item.commerce_item_id).first()
                if existing_commerce_item is not None:
                    existing_reservation_id = existing_commerce_item.capacity_reservation_id

            source_key = f"ticket-item:{item.pk}"
            reservation = _resolve_reservation(
                CapacityReservation,
                existing_reservation_id=existing_reservation_id,
                pool_id=ticket_type.capacity_pool_id,
                journey_id=order.journey_id,
                source_key=source_key,
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

            if existing_commerce_item is None:
                matches = CommerceOrderItem.objects.filter(
                    order_id=commerce_order.pk,
                    offer_id=ticket_type.offer_id,
                ).order_by("pk")
                match_count = matches.count()
                if match_count > 1:
                    raise RuntimeError(
                        "Ambiguous canonical CommerceOrderItem rows for one legacy TicketOrderItem."
                    )
                existing_commerce_item = matches.first()

            if existing_commerce_item is None:
                existing_commerce_item = CommerceOrderItem.objects.create(
                    order_id=commerce_order.pk,
                    offer_id=ticket_type.offer_id,
                    beneficiary_id=order.buyer_id,
                    capacity_reservation_id=reservation.pk,
                    quantity=item.quantity,
                    label_snapshot=ticket_type.name or "Tarif",
                    unit_price=item.unit_price,
                    line_subtotal=line_subtotal,
                    discount_total=line_discount,
                    line_total=line_subtotal - line_discount,
                )

            TicketOrderItem.objects.filter(pk=item.pk).update(
                commerce_item_id=existing_commerce_item.pk
            )


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("tickets", "0007_commerce_capacity_bridges"),
    ]
    operations = [migrations.RunPython(backfill_commerce_capacity, noop)]
