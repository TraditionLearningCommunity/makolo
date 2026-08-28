from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("payments", "0006_backfill_payment_obligations"),
    ]

    operations = [
        migrations.AlterField(
            model_name="paymentobligation",
            name="commerce_order",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="payment_obligations",
                to="commerce.commerceorder",
            ),
        ),
    ]
