# Additive D5 migration: Project context and historical Dossier links only; no backfill.
import uuid

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("objectives", "0003_dossierassignment"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Project",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("title", models.CharField(max_length=220)),
                ("description", models.TextField(blank=True)),
                ("starts_on", models.DateField(blank=True, null=True)),
                ("ends_on", models.DateField(blank=True, null=True)),
                ("lifecycle", models.CharField(choices=[("draft", "Brouillon"), ("active", "Actif"), ("completed", "Terminé"), ("cancelled", "Annulé"), ("archived", "Archivé")], default="draft", max_length=16)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="created_projects", to=settings.AUTH_USER_MODEL)),
                ("owner_profile", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="owned_projects", to=settings.AUTH_USER_MODEL)),
                ("owning_space", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="projects", to="organizations.organization")),
            ],
            options={"ordering": ["-updated_at", "id"]},
        ),
        migrations.CreateModel(
            name="ProjectDossierLink",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("linked_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("is_active", models.BooleanField(default=True)),
                ("removed_at", models.DateTimeField(blank=True, null=True)),
                ("dossier", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="project_links", to="objectives.dossier")),
                ("linked_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="project_dossier_links_created", to=settings.AUTH_USER_MODEL)),
                ("project", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="dossier_links", to="objectives.project")),
                ("removed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="project_dossier_links_removed", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["linked_at", "id"]},
        ),
        migrations.AddConstraint(
            model_name="project",
            constraint=models.CheckConstraint(condition=(models.Q(owner_profile__isnull=False, owning_space__isnull=True) | models.Q(owner_profile__isnull=True, owning_space__isnull=False)), name="project_exactly_one_owner_context"),
        ),
        migrations.AddConstraint(
            model_name="project",
            constraint=models.CheckConstraint(condition=models.Q(starts_on__isnull=True) | models.Q(ends_on__isnull=True) | models.Q(starts_on__lte=models.F("ends_on")), name="project_valid_horizon"),
        ),
        migrations.AddIndex(model_name="project", index=models.Index(fields=["owner_profile", "lifecycle"], name="project_owner_lifecycle_idx")),
        migrations.AddIndex(model_name="project", index=models.Index(fields=["owning_space", "lifecycle"], name="project_space_lifecycle_idx")),
        migrations.AddConstraint(
            model_name="projectdossierlink",
            constraint=models.UniqueConstraint(condition=models.Q(is_active=True), fields=("project", "dossier"), name="project_dossier_active_pair_unique"),
        ),
        migrations.AddConstraint(
            model_name="projectdossierlink",
            constraint=models.UniqueConstraint(condition=models.Q(is_active=True), fields=("dossier",), name="dossier_one_active_project"),
        ),
        migrations.AddIndex(model_name="projectdossierlink", index=models.Index(fields=["project", "is_active"], name="project_dossier_active_idx")),
        migrations.AddIndex(model_name="projectdossierlink", index=models.Index(fields=["dossier", "is_active"], name="dossier_project_active_idx")),
    ]
