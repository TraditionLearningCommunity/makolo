from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("notifications", "0004_push_endpoint"),
    ]

    operations = [
        migrations.AddField(
            model_name="pushendpoint",
            name="device_name",
            field=models.CharField(blank=True, max_length=80),
        ),
    ]
