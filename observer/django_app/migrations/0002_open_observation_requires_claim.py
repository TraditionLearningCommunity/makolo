from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("observer_storage", "0001_initial"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="observation",
            constraint=models.CheckConstraint(
                condition=(
                    ~models.Q(lifecycle="open")
                    | (
                        models.Q(
                            claim_token__isnull=False,
                            lease_expires_at__isnull=False,
                        )
                        & ~models.Q(claimed_by="")
                    )
                ),
                name="obs_open_requires_claim",
            ),
        ),
    ]
