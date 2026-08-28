from django.db import migrations


def backfill_payment_obligations(apps, schema_editor):
    CommerceOrder = apps.get_model("commerce", "CommerceOrder")
    Payment = apps.get_model("payments", "Payment")
    PaymentObligation = apps.get_model("payments", "PaymentObligation")

    orders = CommerceOrder.objects.filter(total__gt=0).order_by("created_at", "id")
    for order in orders.iterator():
        payee_count = int(bool(order.payee_space_id)) + int(bool(order.payee_profile_id))
        if payee_count != 1 or not order.journey_id:
            continue
        source_key = f"commerce:{order.pk}"
        obligation = PaymentObligation.objects.filter(source_key=source_key).first()
        payments = Payment.objects.filter(commerce_order_id=order.pk).order_by("created_at", "id")
        succeeded = payments.filter(status="succeeded").first()
        refunded = payments.filter(status="refunded").first()
        status = "refunded" if refunded else ("satisfied" if succeeded else "pending")
        satisfied_at = succeeded.succeeded_at if succeeded else None
        if obligation is None:
            obligation = PaymentObligation.objects.create(
                journey_id=order.journey_id,
                commerce_order_id=order.pk,
                reason="commerce",
                label=f"Paiement {order.reference}",
                amount=order.total,
                currency=(order.currency or "USD").upper(),
                processing_mode="makolo_provider",
                status=status,
                payee_space_id=order.payee_space_id,
                payee_profile_id=order.payee_profile_id,
                external_payee_name="",
                satisfied_at=satisfied_at,
                source_key=source_key,
            )
        payments.filter(obligation__isnull=True).update(obligation_id=obligation.pk)


def reverse_backfill(apps, schema_editor):
    Payment = apps.get_model("payments", "Payment")
    PaymentObligation = apps.get_model("payments", "PaymentObligation")
    ids = list(PaymentObligation.objects.filter(source_key__startswith="commerce:").values_list("id", flat=True))
    if ids:
        Payment.objects.filter(obligation_id__in=ids).update(obligation_id=None)
        PaymentObligation.objects.filter(id__in=ids).delete()


class Migration(migrations.Migration):
    dependencies = [("payments", "0005_payment_obligations")]

    operations = [migrations.RunPython(backfill_payment_obligations, reverse_backfill)]
