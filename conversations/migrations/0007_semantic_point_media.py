from django.db import migrations, models
import django.db.models.deletion
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [
        ("conversations", "0006_private_attachments"),
    ]

    operations = [
        migrations.AddField(
            model_name="conversationpointattachment",
            name="caption",
            field=models.CharField(blank=True, max_length=5000),
        ),
        migrations.AddField(
            model_name="conversationpointattachment",
            name="option",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                related_name="attachments", to="conversations.conversationpointoption",
            ),
        ),
        migrations.RemoveConstraint(
            model_name="conversationpointattachment",
            name="conv_attachment_not_response_and_exchange",
        ),
        migrations.AddConstraint(
            model_name="conversationpointattachment",
            constraint=models.CheckConstraint(
                condition=(
                    (Q(response__isnull=True) | Q(exchange_entry__isnull=True))
                    & (Q(option__isnull=True) | (
                        Q(response__isnull=True) & Q(exchange_entry__isnull=True)
                    ))
                ),
                name="conv_attachment_single_context",
            ),
        ),
    ]
