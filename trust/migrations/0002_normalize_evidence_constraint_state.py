from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("trust", "0001_initial")]

    operations = [
        migrations.AlterConstraint(
            model_name="trustevidence",
            name="trust_evidence_one_parent",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(("report__isnull", True), ("verification_claim__isnull", False))
                    | models.Q(("report__isnull", False), ("verification_claim__isnull", True))
                ),
                name="trust_evidence_one_parent",
            ),
        ),
    ]
