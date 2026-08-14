import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("access", "0001_initial"),
        ("journeys", "0001_initial"),
        ("tickets", "0004_ticketorder_idempotency"),
    ]

    operations = [
        migrations.AddField(
            model_name="ticketorder",
            name="journey",
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="ticket_order",
                to="journeys.journey",
            ),
        ),
        migrations.AddField(
            model_name="ticket",
            name="access",
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="ticket",
                to="access.access",
            ),
        ),
    ]
