import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("authorization", "0001_initial"),
        ("organizations", "0002_organizationfollow"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Team",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(default="Équipe principale", max_length=160)),
                ("is_default", models.BooleanField(default=False)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="teams", to="organizations.organization")),
            ],
            options={"ordering": ["organization__name", "name"]},
        ),
        migrations.CreateModel(
            name="TeamMembership",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("status", models.CharField(choices=[("invited", "Invité"), ("active", "Actif"), ("inactive", "Inactif")], default="active", max_length=16)),
                ("joined_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("invited_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="team_invitations_sent", to=settings.AUTH_USER_MODEL)),
                ("team", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="memberships", to="organizations.team")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="team_memberships", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["team__organization__name", "user__email"]},
        ),
        migrations.AddConstraint(
            model_name="team",
            constraint=models.UniqueConstraint(fields=("organization", "name"), name="team_org_name_unique"),
        ),
        migrations.AddConstraint(
            model_name="team",
            constraint=models.UniqueConstraint(condition=models.Q(("is_default", True)), fields=("organization",), name="team_one_default_per_org"),
        ),
        migrations.AddIndex(
            model_name="team",
            index=models.Index(fields=["organization", "is_active"], name="team_org_active_idx"),
        ),
        migrations.AddConstraint(
            model_name="teammembership",
            constraint=models.UniqueConstraint(fields=("team", "user"), name="team_membership_unique_user"),
        ),
        migrations.AddIndex(
            model_name="teammembership",
            index=models.Index(fields=["user", "status"], name="team_member_user_status_idx"),
        ),
        migrations.AddIndex(
            model_name="teammembership",
            index=models.Index(fields=["team", "status"], name="team_member_team_status_idx"),
        ),
    ]
