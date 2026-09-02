from django.db import migrations, models

import accounts.validators
import journeys.storage


class Migration(migrations.Migration):
    dependencies = [("trust", "0002_normalize_evidence_constraint_state")]

    operations = [
        migrations.AlterField(
            model_name="trustevidence",
            name="file",
            field=models.FileField(
                storage=journeys.storage.private_artifact_storage,
                upload_to="trust/private-evidence/%Y/%m/",
                validators=[accounts.validators.validate_verification_document],
            ),
        ),
    ]
