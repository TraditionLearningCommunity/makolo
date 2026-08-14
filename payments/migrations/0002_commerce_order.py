from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("commerce", "0001_initial"),
        ("payments", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="payment",
            name="commerce_order",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="payments", to="commerce.commerceorder"),
        ),
        migrations.AddIndex(
            model_name="payment",
            index=models.Index(fields=["commerce_order", "status"], name="pay_commerce_status_idx"),
        ),
        migrations.AddConstraint(
            model_name="payment",
            constraint=models.UniqueConstraint(condition=models.Q(("commerce_order__isnull", False), ("status", "succeeded")), fields=("commerce_order",), name="payment_one_success_commerce_order"),
        ),
    ]
