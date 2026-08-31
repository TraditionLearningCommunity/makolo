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


def add_field_with_db_default(*, name, database_field, state_field):
    """Keep DB defaults visible to both historical writers and migration state."""
    return migrations.SeparateDatabaseAndState(
        database_operations=[
            migrations.AddField(
                model_name="commerceorder",
                name=name,
                field=database_field,
            )
        ],
        state_operations=[
            migrations.AddField(
                model_name="commerceorder",
                name=name,
                field=state_field,
            )
        ],
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
        add_field_with_db_default(
            name="pricing_policy",
            database_field=models.CharField(
                choices=[
                    ("seller_net_guaranteed", "Net bénéficiaire garanti"),
                    ("customer_total_fixed", "Total client fixé"),
                ],
                default="seller_net_guaranteed",
                db_default="seller_net_guaranteed",
                max_length=32,
            ),
            state_field=models.CharField(
                choices=[
                    ("seller_net_guaranteed", "Net bénéficiaire garanti"),
                    ("customer_total_fixed", "Total client fixé"),
                ],
                default="seller_net_guaranteed",
                db_default="seller_net_guaranteed",
                max_length=32,
            ),
        ),
        add_field_with_db_default(
            name="expected_payee_amount",
            database_field=models.DecimalField(
                decimal_places=2,
                default=Decimal("0.00"),
                db_default=Decimal("0.00"),
                max_digits=12,
            ),
            state_field=models.DecimalField(
                decimal_places=2,
                default=Decimal("0.00"),
                db_default=Decimal("0.00"),
                max_digits=12,
            ),
        ),
        add_field_with_db_default(
            name="makolo_amount",
            database_field=models.DecimalField(
                decimal_places=2,
                default=Decimal("0.00"),
                db_default=Decimal("0.00"),
                max_digits=12,
            ),
            state_field=models.DecimalField(
                decimal_places=2,
                default=Decimal("0.00"),
                db_default=Decimal("0.00"),
                max_digits=12,
            ),
        ),
        add_field_with_db_default(
            name="financial_snapshot",
            database_field=models.JSONField(
                blank=True,
                default=dict,
                db_default={},
            ),
            state_field=models.JSONField(
                blank=True,
                default=dict,
                db_default={},
            ),
        ),
        migrations.AddConstraint(
            model_name="commerceorder",
            constraint=models.CheckConstraint(
                condition=models.Q(expected_payee_amount__gte=0),
                name="commerce_order_payee_nonnegative",
            ),
        ),
        migrations.AddConstraint(
            model_name="commerceorder",
            constraint=models.CheckConstraint(
                condition=models.Q(makolo_amount__gte=0),
                name="commerce_order_makolo_nonnegative",
            ),
        ),
        migrations.RunPython(backfill_financial_snapshots, migrations.RunPython.noop),
    ]
