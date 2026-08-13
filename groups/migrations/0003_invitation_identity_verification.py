from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("groups", "0002_group_slug_blank"),
    ]

    operations = [
        migrations.AddField(
            model_name="groupinvitation",
            name="verification_digest",
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name="groupinvitation",
            name="verification_expires_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="groupinvitation",
            name="identity_verified_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
