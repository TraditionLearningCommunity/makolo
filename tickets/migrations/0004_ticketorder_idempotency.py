from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tickets", "0003_ticketwaitlistentry_tickettransfer"),
    ]

    operations = [
        migrations.AddField(
            model_name="ticketorder",
            name="idempotency_fingerprint",
            field=models.CharField(blank=True, editable=False, max_length=64),
        ),
        migrations.AddField(
            model_name="ticketorder",
            name="idempotency_key",
            field=models.UUIDField(blank=True, editable=False, null=True, unique=True),
        ),
    ]
