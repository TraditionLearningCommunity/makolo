import uuid

from django.conf import settings
from django.db import migrations, models
from django.db.models import Q
import django.db.models.deletion
from journeys.storage import private_artifact_storage
from questionnaires.media_models import questionnaire_media_path


class Migration(migrations.Migration):
    dependencies = [
        ("questionnaires", "0002_profile_targeted_requests"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="QuestionnaireMedia",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("choice_index", models.PositiveIntegerField(null=True, blank=True)),
                ("position", models.PositiveIntegerField(default=0)),
                ("caption", models.CharField(max_length=5000, blank=True)),
                ("kind", models.CharField(max_length=16, choices=[
                    ("image", "Image"), ("video", "Vidéo"), ("audio", "Audio"),
                    ("voice", "Note vocale"), ("file", "Document"),
                ])),
                ("file", models.FileField(storage=private_artifact_storage, upload_to=questionnaire_media_path, max_length=500)),
                ("original_name", models.CharField(max_length=255)),
                ("mime_type", models.CharField(max_length=180)),
                ("size", models.PositiveBigIntegerField()),
                ("content_hash", models.CharField(max_length=64)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("form_version", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="media", to="questionnaires.formversion")),
                ("question", models.ForeignKey(null=True, blank=True, on_delete=django.db.models.deletion.PROTECT, related_name="media", to="questionnaires.formquestion")),
                ("uploaded_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="questionnaire_media", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["position", "created_at", "id"]},
        ),
        migrations.AddConstraint(
            model_name="questionnairemedia",
            constraint=models.CheckConstraint(
                condition=Q(choice_index__isnull=True) | Q(question__isnull=False),
                name="qnr_media_choice_requires_question",
            ),
        ),
    ]
