import accounts.models
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="user",
            name="phone",
            field=models.CharField(
                blank=True,
                max_length=30,
                null=True,
                validators=[accounts.models.validate_phone_number],
            ),
        ),
        migrations.AlterField(
            model_name="userprofile",
            name="theme",
            field=models.CharField(default="system", max_length=50),
        ),
    ]
