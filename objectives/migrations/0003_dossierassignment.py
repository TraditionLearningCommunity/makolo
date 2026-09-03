# Additive D3 migration: responsibility only, no authority backfill.
import uuid

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("objectives", "0002_dossierjourneydependency"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="DossierAssignment",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("assigned_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("status", models.CharField(choices=[("active", "Active"), ("removed", "Retirée")], default="active", max_length=16)),
                ("removed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("assignee", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="dossier_assignments", to=settings.AUTH_USER_MODEL)),
                ("assigned_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="dossier_assignments_created", to=settings.AUTH_USER_MODEL)),
                ("dossier", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="assignments", to="objectives.dossier")),
                ("removed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="dossier_assignments_removed", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["assigned_at", "id"]},
        ),
        migrations.AddConstraint(
            model_name="dossierassignment",
            constraint=models.UniqueConstraint(condition=models.Q(status="active"), fields=("dossier", "assignee"), name="dossier_assignment_active_unique"),
        ),
        migrations.AddIndex(model_name="dossierassignment", index=models.Index(fields=["dossier", "status"], name="dossier_assign_status_idx")),
        migrations.AddIndex(model_name="dossierassignment", index=models.Index(fields=["assignee", "status"], name="dossier_assignee_status_idx")),
    ]
