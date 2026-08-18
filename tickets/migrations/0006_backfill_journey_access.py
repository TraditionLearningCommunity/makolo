import uuid

from django.db import migrations


NAMESPACE = uuid.UUID("229c9f51-28bf-4bc6-96ca-2850bbd356d6")


def stable_id(kind, source_id):
    return uuid.uuid5(NAMESPACE, f"{kind}:{source_id}")


def profile_for_email(User, email):
    email = (email or "").strip()
    if not email:
        return None
    return User.objects.filter(email__iexact=email, is_active=True).values_list("pk", flat=True).first()


def backfill_journey_access(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    Event = apps.get_model("events", "Event")
    Occurrence = apps.get_model("activities", "Occurrence")
    Journey = apps.get_model("journeys", "Journey")
    Access = apps.get_model("access", "Access")
    TicketOrder = apps.get_model("tickets", "TicketOrder")
    Ticket = apps.get_model("tickets", "Ticket")

    order_status_map = {
        "pending": "pending_payment",
        "cancelled": "cancelled",
        "expired": "expired",
    }
    ticket_status_map = {
        "valid": "valid",
        "used": "used",
        "cancelled": "cancelled",
        "refunded": "revoked",
    }

    for order in TicketOrder.objects.all().order_by("pk").iterator():
        event = Event.objects.filter(pk=order.event_id).only("activity_id").first()
        if event is None or event.activity_id is None:
            continue
        beneficiary_id = order.buyer_id or profile_for_email(User, order.customer_email)
        if beneficiary_id is None:
            continue
        occurrence_id = (
            Occurrence.objects.filter(activity_id=event.activity_id)
            .order_by("start_at", "pk")
            .values_list("pk", flat=True)
            .first()
        )
        if order.status == "confirmed":
            journey_status = "fulfilled" if Ticket.objects.filter(order_id=order.pk).exists() else "confirmed"
        else:
            journey_status = order_status_map.get(order.status)
        if journey_status is None:
            continue
        journey_id = stable_id("ticket-order-journey", order.pk)
        Journey.objects.update_or_create(
            pk=journey_id,
            defaults={
                "initiated_by_id": beneficiary_id,
                "beneficiary_id": beneficiary_id,
                "activity_id": event.activity_id,
                "occurrence_id": occurrence_id,
                "workflow": "purchase",
                "status": journey_status,
                "expires_at": order.expires_at,
            },
        )
        TicketOrder.objects.filter(pk=order.pk).update(journey_id=journey_id)

    for ticket in Ticket.objects.all().order_by("pk").iterator():
        # Load the Event using the registry supplied to the migration. In the
        # historical state `end_at` is a stored field; after the Event cutover
        # it is a compatibility projection backed by the primary Occurrence.
        # Avoid restricting the query to a field that no longer exists on the
        # current model so the backfill remains safely re-runnable in tests.
        event = Event.objects.filter(pk=ticket.event_id).first()
        if event is None or event.activity_id is None:
            continue
        beneficiary_id = (
            ticket.owner_id
            or profile_for_email(User, ticket.holder_email)
            or TicketOrder.objects.filter(pk=ticket.order_id).values_list("buyer_id", flat=True).first()
        )
        if beneficiary_id is None:
            continue
        occurrence_id = (
            Occurrence.objects.filter(activity_id=event.activity_id)
            .order_by("start_at", "pk")
            .values_list("pk", flat=True)
            .first()
        )
        journey_id = TicketOrder.objects.filter(pk=ticket.order_id).values_list("journey_id", flat=True).first()
        access_status = ticket_status_map.get(ticket.status)
        if access_status is None:
            continue
        access_id = stable_id("ticket-access", ticket.pk)
        Access.objects.update_or_create(
            pk=access_id,
            defaults={
                "beneficiary_id": beneficiary_id,
                "activity_id": event.activity_id,
                "occurrence_id": occurrence_id,
                "journey_id": journey_id,
                "issued_by_id": None,
                "status": access_status,
                "single_use": True,
                "source_key": f"ticket:{ticket.pk}",
                "valid_from": None,
                "valid_until": event.end_at,
            },
        )
        Ticket.objects.filter(pk=ticket.pk).update(access_id=access_id)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("events", "0005_backfill_activity_occurrence"),
        ("tickets", "0005_journey_access_bridges"),
    ]
    operations = [migrations.RunPython(backfill_journey_access, noop)]
