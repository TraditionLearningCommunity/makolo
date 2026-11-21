from django.db import migrations, models
from django.db.models import Q
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("journeys", "0005_journey_plan_templates"),
        ("organizations", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="journey",
            name="beneficiary_space",
            field=models.ForeignKey(
                to="organizations.organization",
                on_delete=django.db.models.deletion.PROTECT,
                related_name="beneficiary_journeys",
                null=True,
                blank=True,
            ),
        ),
        migrations.RemoveConstraint(
            model_name="journey",
            name="journey_exactly_one_beneficiary",
        ),
        migrations.AddConstraint(
            model_name="journey",
            constraint=models.CheckConstraint(
                condition=(
                    Q(beneficiary__isnull=False, external_beneficiary__isnull=True, beneficiary_space__isnull=True)
                    | Q(beneficiary__isnull=True, external_beneficiary__isnull=False, beneficiary_space__isnull=True)
                    | Q(beneficiary__isnull=True, external_beneficiary__isnull=True, beneficiary_space__isnull=False)
                ),
                name="journey_exactly_one_beneficiary",
            ),
        ),
        migrations.AddIndex(
            model_name="journey",
            index=models.Index(
                fields=["beneficiary_space", "status"],
                name="journey_spcben_status_idx",
            ),
        ),
    ]
