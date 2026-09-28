# Generated for Makolo identity foundation.

import accounts.validators
from django.db import migrations, models
from django.db.models import Q
from django.db.models.functions import Lower


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0006_remove_legacy_account_truths"),
    ]

    operations = [
        migrations.AlterField(
            model_name="user",
            name="email",
            field=models.EmailField(blank=True, max_length=254, null=True),
        ),
        migrations.AlterField(
            model_name="user",
            name="username",
            field=models.CharField(
                max_length=150,
                unique=True,
                validators=[accounts.validators.validate_makolo_username],
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="username_configured",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="user",
            name="username_changed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddConstraint(
            model_name="user",
            constraint=models.UniqueConstraint(
                Lower("username"),
                name="accounts_user_username_ci_unique",
            ),
        ),
        migrations.AddConstraint(
            model_name="user",
            constraint=models.UniqueConstraint(
                Lower("email"),
                condition=Q(email__isnull=False) & ~Q(email=""),
                name="accounts_user_email_ci_unique",
            ),
        ),
    ]
