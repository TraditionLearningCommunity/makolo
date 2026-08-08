import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Organization",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=180)),
                ("slug", models.SlugField(blank=True, max_length=200, unique=True)),
                ("description", models.TextField(blank=True)),
                ("website", models.URLField(blank=True)),
                ("contact_email", models.EmailField(blank=True, max_length=254)),
                ("contact_phone", models.CharField(blank=True, max_length=40)),
                ("country", models.CharField(blank=True, max_length=120)),
                ("city", models.CharField(blank=True, max_length=120)),
                ("public_profile", models.BooleanField(default=True)),
                ("verification_status", models.CharField(choices=[("new", "Nouveau"), ("pending", "Vérification en cours"), ("verified", "Vérifié"), ("suspended", "Suspendu")], default="new", max_length=20)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="created_organizations", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="OrganizationMembership",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("role", models.CharField(choices=[("owner", "Propriétaire"), ("admin", "Administrateur"), ("event_manager", "Gestionnaire d'événements"), ("finance", "Finance"), ("marketing", "Marketing / Communication"), ("scanner_manager", "Responsable accès")], default="event_manager", max_length=24)),
                ("is_active", models.BooleanField(default=True)),
                ("joined_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("invited_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="organization_invitations_sent", to=settings.AUTH_USER_MODEL)),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="memberships", to="organizations.organization")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="organization_memberships", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["organization__name", "user__email"]},
        ),
        migrations.AddIndex(
            model_name="organization",
            index=models.Index(fields=["verification_status", "public_profile"], name="organizatio_verific_68b188_idx"),
        ),
        migrations.AddIndex(
            model_name="organization",
            index=models.Index(fields=["created_at"], name="organizatio_created_dde2e1_idx"),
        ),
        migrations.AddConstraint(
            model_name="organizationmembership",
            constraint=models.UniqueConstraint(fields=("organization", "user"), name="organization_membership_unique_user"),
        ),
        migrations.AddIndex(
            model_name="organizationmembership",
            index=models.Index(fields=["user", "is_active"], name="organizatio_user_id_d45739_idx"),
        ),
        migrations.AddIndex(
            model_name="organizationmembership",
            index=models.Index(fields=["organization", "role", "is_active"], name="organizatio_organiz_25f1f7_idx"),
        ),
    ]
