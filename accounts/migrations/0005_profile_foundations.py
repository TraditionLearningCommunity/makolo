from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0004_service_opportunity_notification_preferences"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="tiktok_url",
            field=models.URLField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="user",
            name="youtube_url",
            field=models.URLField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="userprofile",
            name="searchable",
            field=models.BooleanField(default=False),
        ),
    ]
