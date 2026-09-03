import uuid

import django.db.models.deletion
from django.db import migrations, models
from django.db.models import Q


SCOPE_CHOICES = [
    ("platform", "Plateforme Makolo"),
    ("space", "Espace"),
    ("group", "Groupe"),
    ("activity", "Activité"),
    ("dossier", "Dossier"),
]

NAMESPACE = uuid.UUID("02fbb4da-f266-4a4d-b843-1363019302fb")


def stable_uuid(kind, code):
    return uuid.uuid5(NAMESPACE, f"{kind}:{code}")


PERMISSIONS = (
    ("dossier.view", "Voir ce Dossier"),
    ("dossier.manage", "Gérer ce Dossier"),
    ("dossier.authority.manage", "Gérer les accès à ce Dossier"),
)

ROLE_BUNDLES = {
    "dossier-viewer": ("Lecteur du dossier", {"dossier.view"}),
    "dossier-manager": ("Responsable du dossier", {"dossier.view", "dossier.manage"}),
    "dossier-admin": (
        "Administrateur du dossier",
        {"dossier.view", "dossier.manage", "dossier.authority.manage"},
    ),
}


def seed_dossier_authority(apps, schema_editor):
    Permission = apps.get_model("authorization", "Permission")
    Role = apps.get_model("authorization", "Role")
    RolePermission = apps.get_model("authorization", "RolePermission")

    permissions = {}
    for code, name in PERMISSIONS:
        permission, _ = Permission.objects.get_or_create(
            code=code,
            defaults={"id": stable_uuid("permission", code)},
        )
        permission.name = name
        permission.description = "Permission système du bounded context Objectives Makolo."
        permission.domain = "objectives"
        permission.scope_type = "dossier"
        permission.is_system = True
        permission.is_active = True
        permission.save()
        permissions[code] = permission

    for role_code, (name, permission_codes) in ROLE_BUNDLES.items():
        role, _ = Role.objects.get_or_create(
            code=role_code,
            scope_type="dossier",
            is_system=True,
            defaults={
                "id": stable_uuid("role", role_code),
                "name": name,
                "description": "Autorité système limitée à un Dossier précis.",
                "organization_id": None,
                "is_active": True,
            },
        )
        role.name = name
        role.description = "Autorité système limitée à un Dossier précis."
        role.organization_id = None
        role.is_active = True
        role.save()
        for code in permission_codes:
            RolePermission.objects.get_or_create(
                role=role,
                permission=permissions[code],
                defaults={"id": stable_uuid("role-permission", f"{role_code}:{code}")},
            )


class Migration(migrations.Migration):
    dependencies = [
        ("authorization", "0014_trust_permissions"),
        ("objectives", "0002_dossierjourneydependency"),
    ]

    operations = [
        migrations.AlterField(
            model_name="permission",
            name="scope_type",
            field=models.CharField(choices=SCOPE_CHOICES, max_length=16),
        ),
        migrations.AlterField(
            model_name="role",
            name="scope_type",
            field=models.CharField(choices=SCOPE_CHOICES, max_length=16),
        ),
        migrations.AlterField(
            model_name="mandate",
            name="scope_type",
            field=models.CharField(choices=SCOPE_CHOICES, max_length=16),
        ),
        migrations.AddField(
            model_name="mandate",
            name="dossier",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="authority_mandates",
                to="objectives.dossier",
            ),
        ),
        migrations.AlterModelOptions(
            name="mandate",
            options={
                "ordering": [
                    "scope_type",
                    "space__name",
                    "group__name",
                    "activity__title",
                    "dossier__title",
                    "profile__email",
                    "role__name",
                ]
            },
        ),
        migrations.RemoveConstraint(model_name="role", name="auth_role_scope_organization_valid"),
        migrations.AddConstraint(
            model_name="role",
            constraint=models.CheckConstraint(
                condition=(
                    Q(scope_type="platform", is_system=True, organization__isnull=True)
                    | Q(scope_type="space", is_system=True, organization__isnull=True)
                    | Q(scope_type="space", is_system=False, organization__isnull=False)
                    | Q(scope_type="group", is_system=True, organization__isnull=True)
                    | Q(scope_type="activity", is_system=True, organization__isnull=True)
                    | Q(scope_type="dossier", is_system=True, organization__isnull=True)
                ),
                name="auth_role_scope_organization_valid",
            ),
        ),
        migrations.RemoveConstraint(model_name="mandate", name="auth_mandate_scope_target_valid"),
        migrations.AddConstraint(
            model_name="mandate",
            constraint=models.CheckConstraint(
                condition=(
                    Q(
                        scope_type="platform",
                        space__isnull=True,
                        group__isnull=True,
                        activity__isnull=True,
                        dossier__isnull=True,
                    )
                    | Q(
                        scope_type="space",
                        space__isnull=False,
                        group__isnull=True,
                        activity__isnull=True,
                        dossier__isnull=True,
                    )
                    | Q(
                        scope_type="group",
                        space__isnull=True,
                        group__isnull=False,
                        activity__isnull=True,
                        dossier__isnull=True,
                    )
                    | Q(
                        scope_type="activity",
                        space__isnull=True,
                        group__isnull=True,
                        activity__isnull=False,
                        dossier__isnull=True,
                    )
                    | Q(
                        scope_type="dossier",
                        space__isnull=True,
                        group__isnull=True,
                        activity__isnull=True,
                        dossier__isnull=False,
                    )
                ),
                name="auth_mandate_scope_target_valid",
            ),
        ),
        migrations.AddConstraint(
            model_name="mandate",
            constraint=models.UniqueConstraint(
                fields=("profile", "role", "scope_type", "dossier"),
                condition=Q(scope_type="dossier", status="active"),
                name="auth_mandate_active_dossier_unique",
            ),
        ),
        migrations.AddIndex(
            model_name="mandate",
            index=models.Index(fields=["dossier", "status"], name="auth_mand_dos_status_idx"),
        ),
        migrations.RunPython(seed_dossier_authority, migrations.RunPython.noop),
    ]
