import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("tickets", "0009_validate_ticket_type_canonical"),
    ]

    operations = [
        migrations.AlterField(
            model_name="tickettype",
            name="offer",
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="ticket_type",
                to="commerce.offer",
            ),
        ),
        migrations.AlterField(
            model_name="tickettype",
            name="capacity_pool",
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="ticket_type",
                to="capacity.capacitypool",
            ),
        ),
        migrations.RemoveField(model_name="tickettype", name="price"),
        migrations.RemoveField(model_name="tickettype", name="currency"),
        migrations.RemoveField(model_name="tickettype", name="quantity_total"),
        migrations.RemoveField(model_name="tickettype", name="reserved_quantity"),
        migrations.RemoveField(model_name="tickettype", name="issued_quantity"),
        migrations.RemoveField(model_name="tickettype", name="sales_start_at"),
        migrations.RemoveField(model_name="tickettype", name="sales_end_at"),
        migrations.RemoveField(model_name="tickettype", name="min_per_order"),
        migrations.RemoveField(model_name="tickettype", name="max_per_order"),
        migrations.RemoveField(model_name="tickettype", name="is_active"),
        migrations.AlterModelOptions(
            name="tickettype",
            options={
                "ordering": ["name", "id"],
                "verbose_name": "type de billet",
                "verbose_name_plural": "types de billets",
            },
        ),
    ]
