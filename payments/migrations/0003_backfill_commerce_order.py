from django.db import migrations


def backfill_payment_commerce(apps, schema_editor):
    Payment = apps.get_model("payments", "Payment")
    TicketOrder = apps.get_model("tickets", "TicketOrder")
    for payment in Payment.objects.filter(commerce_order_id__isnull=True).order_by("pk").iterator():
        commerce_order_id = TicketOrder.objects.filter(pk=payment.order_id).values_list("commerce_order_id", flat=True).first()
        if commerce_order_id:
            Payment.objects.filter(pk=payment.pk).update(commerce_order_id=commerce_order_id)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("payments", "0002_commerce_order"),
        ("tickets", "0008_backfill_commerce_capacity"),
    ]
    operations = [migrations.RunPython(backfill_payment_commerce, noop)]
