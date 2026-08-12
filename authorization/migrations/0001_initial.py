import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("organizations", "0002_organizationfollow"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Permission",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("code", models.CharField(max_length=120, unique=True)),
                ("name", models.CharField(max_length=160)),
                ("description", models.TextField(blank=True)),
                ("domain", models.CharField(max_length=80)),
                ("scope_type", models.CharField(choices=[("platform", "Plateforme Makolo"), ("space", "Espace")], max_length=16)),
                ("is_system", models.BooleanField(default=True)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["domain", "code"]},
        ),
        migrations.CreateModel(
            name="Role",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("code", models.SlugField(max_length=120)),
                ("name", models.CharField(max_length=160)),
                ("description", models.TextField(blank=True)),
                ("scope_type", models.CharField(choices=[("platform", "Plateforme Makolo"), ("space", "Espace")], max_length=16)),
                ("is_system", models.BooleanField(default=False)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("organization", models.ForeignKey(blank=True, help_text="Renseigné uniquement pour un rôle personnalisé propre à un Espace.", null=True, on_delete=django.db.models.deletion.CASCADE, related_name="custom_authorization_roles", to="organizations.organization")),
            ],
            options={"ordering": ["scope_type", "name"]},
        ),
        migrations.CreateModel(
            name="RolePermission",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("permission", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="role_permissions", to="authorization.permission")),
                ("role", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="role_permissions", to="authorization.role")),
            ],
            options={"ordering": ["role__name", "permission__code"]},
        ),
        migrations.AddField(
            model_name="role",
            name="permissions",
            field=models.ManyToManyField(blank=True, related_name="roles", through="authorization.RolePermission", to="authorization.permission"),
        ),
        migrations.CreateModel(
            name="Mandate",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("scope_type", models.CharField(choices=[("platform", "Plateforme Makolo"), ("space", "Espace")], max_length=16)),
                ("status", models.CharField(choices=[("active", "Actif"), ("suspended", "Suspendu"), ("revoked", "Révoqué")], default="active", max_length=16)),
                ("valid_from", models.DateTimeField(blank=True, null=True)),
                ("valid_until", models.DateTimeField(blank=True, null=True)),
                ("granted_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                ("source", models.CharField(default="service", max_length=80)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("granted_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="authority_mandates_granted", to=settings.AUTH_USER_MODEL)),
                ("profile", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="authority_mandates", to=settings.AUTH_USER_MODEL)),
                ("role", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="mandates", to="authorization.role")),
                ("space", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="authority_mandates", to="organizations.organization")),
            ],
            options={"ordering": ["scope_type", "space__name", "profile__email", "role__name"]},
        ),
        migrations.AddConstraint(
            model_name="role",
            constraint=models.UniqueConstraint(condition=models.Q(("is_system", True)), fields=("code",), name="auth_role_system_code_unique"),
        ),
        migrations.AddConstraint(
            model_name="role",
            constraint=models.UniqueConstraint(condition=models.Q(("is_system", False)), fields=("organization", "code"), name="auth_role_custom_space_code_unique"),
        ),
        migrations.AddConstraint(
            model_name="role",
            constraint=models.CheckConstraint(condition=models.Q(models.Q(("is_system", True), ("organization__isnull", True), ("scope_type", "platform")), models.Q(("is_system", True), ("organization__isnull", True), ("scope_type", "space")), models.Q(("is_system", False), ("organization__isnull", False), ("scope_type", "space")), _connector="OR"), name="auth_role_scope_organization_valid"),
        ),
        migrations.AddIndex(
            model_name="role",
            index=models.Index(fields=["scope_type", "is_active"], name="auth_role_scope_active_idx"),
        ),
        migrations.AddIndex(
            model_name="role",
            index=models.Index(fields=["organization", "is_active"], name="auth_role_org_active_idx"),
        ),
        migrations.AddConstraint(
            model_name="rolepermission",
            constraint=models.UniqueConstraint(fields=("role", "permission"), name="auth_role_permission_unique"),
        ),
        migrations.AddIndex(
            model_name="rolepermission",
            index=models.Index(fields=["permission", "role"], name="auth_role_perm_lookup_idx"),
        ),
        migrations.AddIndex(
            model_name="permission",
            index=models.Index(fields=["scope_type", "is_active"], name="auth_perm_scope_active_idx"),
        ),
        migrations.AddIndex(
            model_name="permission",
            index=models.Index(fields=["domain", "is_active"], name="auth_perm_domain_active_idx"),
        ),
        migrations.AddConstraint(
            model_name="mandate",
            constraint=models.CheckConstraint(condition=models.Q(models.Q(("scope_type", "platform"), ("space__isnull", True)), models.Q(("scope_type", "space"), ("space__isnull", False)), _connector="OR"), name="auth_mandate_scope_space_valid"),
        ),
        migrations.AddConstraint(
            model_name="mandate",
            constraint=models.CheckConstraint(condition=models.Q(("valid_until__isnull", True), ("valid_from__isnull", True), ("valid_until__gt", models.F("valid_from")), _connector="OR"), name="auth_mandate_valid_window"),
        ),
        migrations.AddConstraint(
            model_name="mandate",
            constraint=models.UniqueConstraint(condition=models.Q(("scope_type", "platform"), ("status", "active")), fields=("profile", "role", "scope_type"), name="auth_mandate_active_platform_unique"),
        ),
        migrations.AddConstraint(
            model_name="mandate",
            constraint=models.UniqueConstraint(condition=models.Q(("scope_type", "space"), ("status", "active")), fields=("profile", "role", "scope_type", "space"), name="auth_mandate_active_space_unique"),
        ),
        migrations.AddIndex(
            model_name="mandate",
            index=models.Index(fields=["profile", "status"], name="auth_mand_prof_status_idx"),
        ),
        migrations.AddIndex(
            model_name="mandate",
            index=models.Index(fields=["scope_type", "status"], name="auth_mandate_scope_status_idx"),
        ),
        migrations.AddIndex(
            model_name="mandate",
            index=models.Index(fields=["space", "status"], name="auth_mandate_space_status_idx"),
        ),
        migrations.AddIndex(
            model_name="mandate",
            index=models.Index(fields=["valid_from", "valid_until"], name="auth_mandate_validity_idx"),
        ),
    ]
