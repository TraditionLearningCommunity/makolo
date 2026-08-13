import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.db.models import Q

import geography.validators


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        ("organizations", "0003_team_teammembership"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.CreateModel(
            name="Activity",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("title", models.CharField(max_length=220)),
                ("slug", models.SlugField(blank=True, max_length=240)),
                ("short_description", models.CharField(blank=True, max_length=320)),
                ("description", models.TextField(blank=True)),
                ("status", models.CharField(choices=[("draft", "Brouillon"), ("published", "Publiée"), ("cancelled", "Annulée"), ("completed", "Terminée"), ("archived", "Archivée")], default="draft", max_length=20)),
                ("visibility", models.CharField(choices=[("public", "Public"), ("unlisted", "Non répertoriée"), ("private", "Privée")], default="public", max_length=20)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_activities", to=settings.AUTH_USER_MODEL)),
                ("space", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="activities", to="organizations.organization")),
            ],
            options={"ordering": ["title", "id"]},
        ),
        migrations.CreateModel(
            name="Occurrence",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("label", models.CharField(blank=True, max_length=180)),
                ("start_at", models.DateTimeField()),
                ("end_at", models.DateTimeField(blank=True, null=True)),
                ("timezone", models.CharField(default="Africa/Lubumbashi", max_length=100, validators=[geography.validators.validate_timezone_name])),
                ("status", models.CharField(choices=[("draft", "Brouillon"), ("scheduled", "Planifiée"), ("cancelled", "Annulée"), ("completed", "Terminée")], default="draft", max_length=20)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("activity", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="occurrences", to="activities.activity")),
            ],
            options={"ordering": ["start_at", "id"]},
        ),
        migrations.AddConstraint(model_name="activity", constraint=models.UniqueConstraint(fields=("space", "slug"), condition=Q(space__isnull=False), name="activities_space_slug_unique")),
        migrations.AddConstraint(model_name="activity", constraint=models.UniqueConstraint(fields=("slug",), condition=Q(space__isnull=True), name="activities_legacy_slug_unique")),
        migrations.AddIndex(model_name="activity", index=models.Index(fields=["space", "status"], name="activities_space_status_idx")),
        migrations.AddIndex(model_name="activity", index=models.Index(fields=["visibility", "status"], name="activities_visibility_idx")),
        migrations.AddConstraint(model_name="occurrence", constraint=models.CheckConstraint(condition=Q(end_at__isnull=True) | Q(end_at__gt=models.F("start_at")), name="activities_occ_end_after_start")),
        migrations.AddConstraint(model_name="occurrence", constraint=models.CheckConstraint(condition=~Q(timezone=""), name="activities_occ_timezone_present")),
        migrations.AddIndex(model_name="occurrence", index=models.Index(fields=["activity", "start_at"], name="activities_occ_activity_idx")),
        migrations.AddIndex(model_name="occurrence", index=models.Index(fields=["status", "start_at"], name="activities_occ_status_idx")),
    ]
