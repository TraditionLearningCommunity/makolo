import uuid

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("sharing", "0006_passport_issued_public_and_sharing"),
        ("space_assets", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="shareenvelope",
            name="subject_type",
            field=models.CharField(
                max_length=24,
                choices=[
                    ("activity", "Activity"),
                    ("opportunity", "Opportunity"),
                    ("journey", "Journey"),
                    ("passport", "Passeport émis"),
                    ("space_document", "Document de l’Espace"),
                ],
            ),
        ),
        migrations.CreateModel(
            name="SpaceDocumentShareSubject",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("envelope", models.OneToOneField(to="sharing.shareenvelope", on_delete=django.db.models.deletion.CASCADE, related_name="space_document_subject")),
                ("version", models.ForeignKey(to="space_assets.spacedocumentversion", on_delete=django.db.models.deletion.PROTECT, related_name="share_subjects")),
            ],
        ),
    ]
