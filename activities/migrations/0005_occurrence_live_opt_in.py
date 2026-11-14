from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("activities", "0004_occurrence_temporal_schedule"),
    ]

    operations = [
        migrations.AddField(
            model_name="occurrence",
            name="live_enabled",
            field=models.BooleanField(default=False),
        ),
    ]
