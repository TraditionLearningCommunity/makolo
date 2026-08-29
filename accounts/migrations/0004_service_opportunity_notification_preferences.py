from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0003_profile_identity_device_key"),
    ]

    operations = [
        migrations.AddField(
            model_name="notificationpreference",
            name="service_notifications",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="notificationpreference",
            name="opportunity_notifications",
            field=models.BooleanField(default=True),
        ),
    ]
