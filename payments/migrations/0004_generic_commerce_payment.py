from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("payments", "0003_backfill_commerce_order"),
    ]

    operations = [
        migrations.AlterField(
            model_name="payment",
            name="order",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="payments", to="tickets.ticketorder"),
        ),
        migrations.AddConstraint(
            model_name="payment",
            constraint=models.CheckConstraint(
                condition=models.Q(order__isnull=False) | models.Q(commerce_order__isnull=False),
                name="payment_has_order_source",
            ),
        ),
    ]
