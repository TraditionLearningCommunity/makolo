# Project invitation is pending intent, never a Mandate until accepted.
import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [
        ("objectives", "0004_project_projectdossierlink"),
        ("authorization", "0019_merge_project_scope_recognition"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ProjectInvitation",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("status", models.CharField(
                    max_length=16, default="pending",
                    choices=[
                        ("pending", "En attente"),
                        ("accepted", "Acceptée"),
                        ("declined", "Refusée"),
                        ("cancelled", "Annulée"),
                    ],
                )),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("responded_at", models.DateTimeField(null=True, blank=True)),
                ("project", models.ForeignKey(
                    to="objectives.project", on_delete=django.db.models.deletion.CASCADE,
                    related_name="invitations",
                )),
                ("invitee", models.ForeignKey(
                    to=settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.CASCADE,
                    related_name="project_invitations_received",
                )),
                ("invited_by", models.ForeignKey(
                    to=settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.PROTECT,
                    related_name="project_invitations_sent",
                )),
                ("role", models.ForeignKey(
                    to="authorization.role", on_delete=django.db.models.deletion.PROTECT,
                    related_name="project_invitations",
                )),
            ],
            options={"ordering": ["-created_at", "id"]},
        ),
        migrations.AddConstraint(
            model_name="projectinvitation",
            constraint=models.UniqueConstraint(
                fields=("project", "invitee"), condition=Q(status="pending"),
                name="project_one_pending_invitation_per_invitee",
            ),
        ),
        migrations.AddIndex(
            model_name="projectinvitation",
            index=models.Index(
                fields=["invitee", "status"], name="proj_inv_invitee_status_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="projectinvitation",
            index=models.Index(
                fields=["project", "status"], name="proj_inv_project_status_idx",
            ),
        ),
    ]
