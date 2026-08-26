import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [
        ("journeys", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ExternalBeneficiary",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("display_name", models.CharField(max_length=180)),
                ("email", models.EmailField(blank=True, max_length=254)),
                ("phone", models.CharField(blank=True, max_length=40)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="created_external_beneficiaries",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["display_name", "id"]},
        ),
        migrations.AlterField(
            model_name="journey",
            name="beneficiary",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="beneficiary_journeys",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="journey",
            name="external_beneficiary",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="journeys",
                to="journeys.externalbeneficiary",
            ),
        ),
        migrations.AddIndex(
            model_name="externalbeneficiary",
            index=models.Index(fields=["created_by", "created_at"], name="journey_extben_creator_idx"),
        ),
        migrations.AddIndex(
            model_name="externalbeneficiary",
            index=models.Index(fields=["email"], name="journey_extben_email_idx"),
        ),
        migrations.AddIndex(
            model_name="journey",
            index=models.Index(fields=["external_beneficiary", "status"], name="journey_extben_status_idx"),
        ),
        migrations.AddConstraint(
            model_name="journey",
            constraint=models.CheckConstraint(
                condition=(Q(beneficiary__isnull=False) & Q(external_beneficiary__isnull=True))
                | (Q(beneficiary__isnull=True) & Q(external_beneficiary__isnull=False)),
                name="journey_exactly_one_beneficiary",
            ),
        ),
    ]
