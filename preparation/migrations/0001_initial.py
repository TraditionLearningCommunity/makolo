import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import preparation.models
import preparation.storage


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("activities", "0003_activity_owner_profile"),
    ]

    operations = [
        migrations.CreateModel(
            name="ActivityResource",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("key", models.SlugField(max_length=120)),
                ("title", models.CharField(max_length=220)),
                ("description", models.TextField(blank=True)),
                ("kind", models.CharField(choices=[("text", "Texte / instructions"), ("url", "Lien externe"), ("file", "Fichier")], max_length=16)),
                ("text_content", models.TextField(blank=True)),
                ("external_url", models.URLField(blank=True, max_length=1000)),
                ("file", models.FileField(blank=True, max_length=500, null=True, storage=preparation.storage.PrivateResourceStorage(), upload_to=preparation.models.resource_upload_to)),
                ("mime_type", models.CharField(blank=True, max_length=180)),
                ("size", models.PositiveBigIntegerField(blank=True, null=True)),
                ("content_hash", models.CharField(blank=True, max_length=64)),
                ("visibility", models.CharField(choices=[("public", "Public"), ("participant", "Participant"), ("restricted", "Restreint")], default="participant", max_length=16)),
                ("status", models.CharField(choices=[("draft", "Brouillon"), ("published", "Publiée"), ("superseded", "Remplacée"), ("retired", "Retirée")], default="draft", max_length=16)),
                ("version", models.PositiveIntegerField(default=1)),
                ("significant_update", models.BooleanField(default=False)),
                ("published_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("activity", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="preparation_resources", to="activities.activity")),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="created_activity_resources", to=settings.AUTH_USER_MODEL)),
                ("occurrence", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="preparation_resources", to="activities.occurrence")),
                ("supersedes", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="superseded_by", to="preparation.activityresource")),
            ],
            options={
                "ordering": ["activity", "occurrence", "key", "version", "created_at"],
                "indexes": [
                    models.Index(fields=["activity", "status", "visibility"], name="prep_resource_activity_vis_idx"),
                    models.Index(fields=["occurrence", "status"], name="prep_resource_occ_status_idx"),
                ],
            },
        ),
        migrations.AddConstraint(
            model_name="activityresource",
            constraint=models.UniqueConstraint(fields=("activity", "key", "version"), condition=models.Q(("occurrence__isnull", True)), name="prep_resource_activity_key_ver_unique"),
        ),
        migrations.AddConstraint(
            model_name="activityresource",
            constraint=models.UniqueConstraint(fields=("occurrence", "key", "version"), condition=models.Q(("occurrence__isnull", False)), name="prep_resource_occ_key_ver_unique"),
        ),
        migrations.AddConstraint(model_name="activityresource", constraint=models.CheckConstraint(condition=models.Q(("version__gte", 1)), name="prep_resource_version_positive")),
    ]
