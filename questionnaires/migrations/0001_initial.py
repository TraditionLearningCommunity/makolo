import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("activities", "0003_activity_owner_profile"),
        ("journeys", "0003_services_core_journey_collaboration"),
    ]

    operations = [
        migrations.CreateModel(
            name="Form",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("key", models.SlugField(max_length=120)),
                ("title", models.CharField(max_length=220)),
                ("description", models.TextField(blank=True)),
                ("status", models.CharField(choices=[("active", "Actif"), ("archived", "Archivé")], default="active", max_length=16)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("activity", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="forms", to="activities.activity")),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="created_questionnaire_forms", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["activity", "key", "created_at"]},
        ),
        migrations.AddConstraint(model_name="form", constraint=models.UniqueConstraint(fields=("activity", "key"), name="questionnaire_form_activity_key_unique")),
        migrations.CreateModel(
            name="FormVersion",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("version", models.PositiveIntegerField()),
                ("status", models.CharField(choices=[("draft", "Brouillon"), ("published", "Publiée"), ("retired", "Retirée")], default="draft", max_length=16)),
                ("title", models.CharField(max_length=220)),
                ("description", models.TextField(blank=True)),
                ("published_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="created_form_versions", to=settings.AUTH_USER_MODEL)),
                ("form", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="versions", to="questionnaires.form")),
            ],
            options={"ordering": ["form", "version"]},
        ),
        migrations.AddConstraint(model_name="formversion", constraint=models.UniqueConstraint(fields=("form", "version"), name="questionnaire_form_version_unique")),
        migrations.AddConstraint(model_name="formversion", constraint=models.CheckConstraint(condition=models.Q(("version__gte", 1)), name="questionnaire_form_version_positive")),
        migrations.CreateModel(
            name="FormQuestion",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("key", models.SlugField(max_length=120)),
                ("label", models.CharField(max_length=240)),
                ("help_text", models.TextField(blank=True)),
                ("question_type", models.CharField(choices=[("short_text", "Texte court"), ("long_text", "Texte long"), ("boolean", "Oui/non"), ("single_choice", "Choix unique"), ("multiple_choice", "Choix multiples"), ("number", "Nombre"), ("date", "Date")], max_length=24)),
                ("position", models.PositiveIntegerField(default=0)),
                ("required", models.BooleanField(default=False)),
                ("min_length", models.PositiveIntegerField(blank=True, null=True)),
                ("max_length", models.PositiveIntegerField(blank=True, null=True)),
                ("min_value", models.DecimalField(blank=True, decimal_places=4, max_digits=18, null=True)),
                ("max_value", models.DecimalField(blank=True, decimal_places=4, max_digits=18, null=True)),
                ("choices", models.JSONField(blank=True, default=list)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("form_version", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="questions", to="questionnaires.formversion")),
            ],
            options={"ordering": ["form_version", "position", "created_at"]},
        ),
        migrations.AddConstraint(model_name="formquestion", constraint=models.UniqueConstraint(fields=("form_version", "key"), name="questionnaire_question_version_key_unique")),
        migrations.AddConstraint(model_name="formquestion", constraint=models.UniqueConstraint(fields=("form_version", "position"), name="questionnaire_question_version_position_unique")),
        migrations.CreateModel(
            name="FormRequest",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("status", models.CharField(choices=[("requested", "Demandé"), ("completed", "Terminé"), ("cancelled", "Annulé")], default="requested", max_length=16)),
                ("required", models.BooleanField(default=True)),
                ("opens_at", models.DateTimeField(blank=True, null=True)),
                ("due_at", models.DateTimeField(blank=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="created_form_requests", to=settings.AUTH_USER_MODEL)),
                ("form_version", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="requests", to="questionnaires.formversion")),
                ("journey", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="form_requests", to="journeys.journey")),
            ],
            options={"ordering": ["journey", "created_at", "id"], "indexes": [models.Index(fields=["journey", "status"], name="qnr_req_journey_status_idx")]},
        ),
        migrations.AddConstraint(model_name="formrequest", constraint=models.UniqueConstraint(fields=("journey", "form_version"), name="questionnaire_request_journey_version_unique")),
        migrations.CreateModel(
            name="FormResponse",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("status", models.CharField(choices=[("draft", "Brouillon"), ("submitted", "Soumis"), ("reopened", "Réouvert")], default="draft", max_length=16)),
                ("submitted_at", models.DateTimeField(blank=True, null=True)),
                ("reopened_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("form_version", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="responses", to="questionnaires.formversion")),
                ("reopened_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="reopened_form_responses", to=settings.AUTH_USER_MODEL)),
                ("request", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="response", to="questionnaires.formrequest")),
                ("respondent", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="form_responses", to=settings.AUTH_USER_MODEL)),
            ],
            options={"indexes": [models.Index(fields=["respondent", "status"], name="qnr_resp_user_status_idx")]},
        ),
        migrations.CreateModel(
            name="FormAnswer",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("value", models.JSONField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("question", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="answers", to="questionnaires.formquestion")),
                ("response", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="answers", to="questionnaires.formresponse")),
            ],
        ),
        migrations.AddConstraint(model_name="formanswer", constraint=models.UniqueConstraint(fields=("response", "question"), name="questionnaire_answer_response_question_unique")),
    ]
