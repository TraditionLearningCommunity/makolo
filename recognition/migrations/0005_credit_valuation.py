from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [
        ("recognition", "0004_align_seed_temporal_semantics"),
    ]

    operations = [
        migrations.CreateModel(
            name="RecognitionCreditValuation",
            fields=[
                ("id", models.PositiveSmallIntegerField(
                    default=1, editable=False, primary_key=True, serialize=False
                )),
                ("currency", models.CharField(max_length=3)),
                ("amount_per_credit", models.DecimalField(
                    decimal_places=8, max_digits=18
                )),
                ("is_active", models.BooleanField(default=False)),
                ("version", models.PositiveIntegerField(default=1)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.AddConstraint(
            model_name="recognitioncreditvaluation",
            constraint=models.CheckConstraint(
                condition=Q(id=1),
                name="rec_value_singleton",
            ),
        ),
        migrations.AddConstraint(
            model_name="recognitioncreditvaluation",
            constraint=models.CheckConstraint(
                condition=Q(amount_per_credit__gt=0),
                name="rec_value_positive_amount",
            ),
        ),
    ]
