from decimal import Decimal

from django.db import migrations, models


def backfill_financial_snapshots(apps, schema_editor):
    CommerceOrder = apps.get_model("commerce", "CommerceOrder")
    for order in CommerceOrder.objects.all().iterator():
        snapshot = {
            "version": 1,
            "currency": order.currency,
            "pricing_policy": "seller_net_guaranteed",
            "subtotal": format(order.subtotal, ".2f"),
            "discount_total": format(order.discount_total, ".2f"),
            "net_base": format(order.total, ".2f"),
            "components": [],
            "payer_total": format(order.total, ".2f"),
            "expected_payee_amount": format(order.total, ".2f"),
            "makolo_amount": "0.00",
            "rounding": "ROUND_HALF_UP",
            "money_quantum": "0.01",
            "source": "legacy_backfill",
        }
        CommerceOrder.objects.filter(pk=order.pk).update(
            pricing_policy="seller_net_guaranteed",
            expected_payee_amount=order.total,
            makolo_amount=Decimal("0.00"),
            financial_snapshot=snapshot,
        )


class Migration(migrations.Migration):
    dependencies = [
        ("commerce", "0002_payment_choices_personal_payee_beneficiary"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="commerceorder",
            name="commerce_order_total_consistent",
        ),
        migrations.AddField(
            model_name="commerceorder",
            name="pricing_policy",
            field=models.CharField(
                choices=[
                    ("seller_net_guaranteed", "Net bénéficiaire garanti"),
                    ("customer_total_fixed", "Total client fixé"),
                ],
                default="seller_net_guaranteed",
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name="commerceorder",
            name="expected_payee_amount",
            field=models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=12),
        ),
        migrations.AddField(
            model_name="commerceorder",
            name="makolo_amount",
            field=models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=12),
        ),
        migrations.AddField(
            model_name="commerceorder",
            name="financial_snapshot",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddConstraint(
            model_name="commerceorder",
            constraint=models.CheckConstraint(
                condition=models.Q(("expected_payee_amount__gte", 0)),
                name="commerce_order_payee_nonnegative",
            ),
        ),
        migrations.AddConstraint(
            model_name="commerceorder",
            constraint=models.CheckConstraint(
                condition=models.Q(("makolo_amount__gte", 0)),
                name="commerce_order_makolo_nonnegative",
            ),
        ),
        migrations.RunPython(backfill_financial_snapshots, migrations.RunPython.noop),
    ]
