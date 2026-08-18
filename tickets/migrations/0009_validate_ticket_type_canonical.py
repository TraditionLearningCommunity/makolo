from django.db import migrations


def validate_ticket_type_canonical(apps, schema_editor):
    TicketType = apps.get_model("tickets", "TicketType")
    Offer = apps.get_model("commerce", "Offer")
    CapacityPool = apps.get_model("capacity", "CapacityPool")
    Occurrence = apps.get_model("activities", "Occurrence")

    for ticket_type in TicketType.objects.all().order_by("pk").iterator():
        event = apps.get_model("events", "Event").objects.filter(pk=ticket_type.event_id).only("activity_id").first()
        if event is None or not event.activity_id:
            raise RuntimeError("Every TicketType must belong to an Event with a canonical Activity.")
        occurrence_id = (
            Occurrence.objects.filter(activity_id=event.activity_id)
            .order_by("start_at", "pk")
            .values_list("pk", flat=True)
            .first()
        )
        if occurrence_id is None:
            raise RuntimeError("Every Event TicketType must resolve a primary Occurrence.")

        pool = CapacityPool.objects.filter(pk=ticket_type.capacity_pool_id).first() if ticket_type.capacity_pool_id else None
        if pool is None:
            pool, _ = CapacityPool.objects.update_or_create(
                source_key=f"ticket-type:{ticket_type.pk}",
                defaults={
                    "activity_id": event.activity_id,
                    "occurrence_id": occurrence_id,
                    "label": ticket_type.name,
                    "total_quantity": ticket_type.quantity_total,
                    "is_active": ticket_type.is_active,
                },
            )
            TicketType.objects.filter(pk=ticket_type.pk).update(capacity_pool_id=pool.pk)
        elif pool.activity_id != event.activity_id or pool.occurrence_id not in {None, occurrence_id}:
            raise RuntimeError("TicketType CapacityPool scope is inconsistent with Event Activity/Occurrence.")

        offer = Offer.objects.filter(pk=ticket_type.offer_id).first() if ticket_type.offer_id else None
        if offer is None:
            offer, _ = Offer.objects.update_or_create(
                source_key=f"ticket-type:{ticket_type.pk}",
                defaults={
                    "activity_id": event.activity_id,
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
            TicketType.objects.filter(pk=ticket_type.pk).update(offer_id=offer.pk)
        elif offer.activity_id != event.activity_id or offer.capacity_pool_id != pool.pk:
            raise RuntimeError("TicketType Offer is inconsistent with its canonical CapacityPool/Event scope.")

    if TicketType.objects.filter(offer_id__isnull=True).exists():
        raise RuntimeError("Task 9 requires every TicketType to have an Offer.")
    if TicketType.objects.filter(capacity_pool_id__isnull=True).exists():
        raise RuntimeError("Task 9 requires every TicketType to have a CapacityPool.")


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("tickets", "0008_backfill_commerce_capacity"),
        ("events", "0007_cutover_event_to_activity"),
    ]

    operations = [
        migrations.RunPython(validate_ticket_type_canonical, noop),
    ]
