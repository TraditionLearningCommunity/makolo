from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("capacity", "0001_initial"),
        ("commerce", "0001_initial"),
        ("tickets", "0006_backfill_journey_access"),
    ]

    operations = [
        migrations.AddField(
            model_name="tickettype",
            name="offer",
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="ticket_type", to="commerce.offer"),
        ),
        migrations.AddField(
            model_name="tickettype",
            name="capacity_pool",
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="ticket_type", to="capacity.capacitypool"),
        ),
        migrations.AddField(
            model_name="ticketorder",
            name="commerce_order",
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="ticket_order", to="commerce.commerceorder"),
        ),
        migrations.AddField(
            model_name="ticketorderitem",
            name="commerce_item",
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="ticket_order_item", to="commerce.commerceorderitem"),
        ),
    ]
