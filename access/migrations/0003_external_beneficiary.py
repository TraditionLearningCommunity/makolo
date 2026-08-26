import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [
        ("access", "0002_accessuse_client_reference"),
        ("journeys", "0002_external_beneficiary"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name="access",
            name="beneficiary",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="access_rights",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="access",
            name="external_beneficiary",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="access_rights",
                to="journeys.externalbeneficiary",
            ),
        ),
        migrations.AddIndex(
            model_name="access",
            index=models.Index(fields=["external_beneficiary", "status"], name="access_extben_status_idx"),
        ),
        migrations.AddConstraint(
            model_name="access",
            constraint=models.CheckConstraint(
                condition=(Q(beneficiary__isnull=False) & Q(external_beneficiary__isnull=True))
                | (Q(beneficiary__isnull=True) & Q(external_beneficiary__isnull=False)),
                name="access_exactly_one_beneficiary",
            ),
        ),
    ]
