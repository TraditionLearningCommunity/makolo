"""Canonical Project-scoped authority; no duplicate Project membership table."""
import uuid

import django.db.models.deletion
from django.db import migrations, models
from django.db.models import Q

CHOICES = [
    ("platform", "Plateforme Makolo"), ("space", "Espace"),
    ("group", "Groupe"), ("activity", "Activité"),
    ("project", "Projet"), ("dossier", "Dossier"),
]
NAMESPACE = uuid.UUID("eb879551-8465-459a-8dba-3df1a63f094f")
PERMISSIONS = [
    ("project.view", "Consulter ce Projet"),
    ("project.manage", "Gérer ce Projet"),
    ("project.authority.manage", "Gérer les accès à ce Projet"),
]
ROLE_BUNDLES = {
    "project-viewer": ("Lecteur du Projet", {"project.view"}),
    "project-manager": ("Responsable du Projet", {"project.view", "project.manage"}),
    "project-admin": ("Administrateur du Projet", {
        "project.view", "project.manage", "project.authority.manage",
    }),
}


def seed_project_authority(apps, schema_editor):
    Permission = apps.get_model("authorization", "Permission")
    Role = apps.get_model("authorization", "Role")
    RolePermission = apps.get_model("authorization", "RolePermission")
    permissions = {}
    for code, name in PERMISSIONS:
        permission, _ = Permission.objects.get_or_create(
            code=code,
            defaults={"id": uuid.uuid5(NAMESPACE, "permission:" + code)},
        )
        permission.name = name
        permission.description = "Autorité canonique limitée à un Projet Makolo."
        permission.domain = "objectives"
        permission.scope_type = "project"
        permission.is_system = True
        permission.is_active = True
        permission.save()
        permissions[code] = permission
    for code, (name, included) in ROLE_BUNDLES.items():
        role, _ = Role.objects.get_or_create(
            code=code, scope_type="project", is_system=True,
            defaults={"id": uuid.uuid5(NAMESPACE, "role:" + code)},
        )
        role.name = name
        role.description = "Mandat local du Projet, sans permission implicite sur ses Dossiers."
        role.organization_id = None
        role.is_active = True
        role.save()
        for permission_code in included:
            RolePermission.objects.get_or_create(
                role=role, permission=permissions[permission_code],
                defaults={"id": uuid.uuid5(NAMESPACE, "role-permission:" + code + ":" + permission_code)},
            )


def reverse_project_authority(apps, schema_editor):
    """Undo only this migration's seed, never erase real Project history.

    Downgrading the schema with remaining Project Mandates would erase their
    target and make their scope invalid under the former check constraint.
    """
    from django.db.migrations.exceptions import IrreversibleError

    Permission = apps.get_model("authorization", "Permission")
    Role = apps.get_model("authorization", "Role")
    RolePermission = apps.get_model("authorization", "RolePermission")
    Mandate = apps.get_model("authorization", "Mandate")

    if Mandate.objects.filter(scope_type="project").exists():
        raise IrreversibleError(
            "Project Mandates exist. Preserve or explicitly migrate their "
            "history before reversing authorization.0018_project_scope."
        )

    role_ids = [
        uuid.uuid5(NAMESPACE, "role:" + code) for code in ROLE_BUNDLES
    ]
    permission_ids = [
        uuid.uuid5(NAMESPACE, "permission:" + code)
        for code, _ in PERMISSIONS
    ]
    if Role.objects.filter(scope_type="project").exclude(
        pk__in=role_ids,
    ).exists() or Permission.objects.filter(scope_type="project").exclude(
        pk__in=permission_ids,
    ).exists():
        raise IrreversibleError(
            "Untracked Project roles or permissions require an explicit "
            "data migration before downgrade."
        )
    if RolePermission.objects.filter(
        permission_id__in=permission_ids,
    ).exclude(role_id__in=role_ids).exists():
        raise IrreversibleError(
            "Project permissions are still linked to other roles."
        )

    RolePermission.objects.filter(role_id__in=role_ids).delete()
    Role.objects.filter(pk__in=role_ids).delete()
    Permission.objects.filter(pk__in=permission_ids).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("authorization", "0017_conversation_permissions"),
        ("objectives", "0004_project_projectdossierlink"),
    ]
    operations = [
        migrations.AlterField(model_name="permission", name="scope_type", field=models.CharField(max_length=16, choices=CHOICES)),
        migrations.AlterField(model_name="role", name="scope_type", field=models.CharField(max_length=16, choices=CHOICES)),
        migrations.AlterField(model_name="mandate", name="scope_type", field=models.CharField(max_length=16, choices=CHOICES)),
        migrations.AddField(
            model_name="mandate", name="project",
            field=models.ForeignKey(
                to="objectives.project", null=True, blank=True,
                related_name="authority_mandates", on_delete=django.db.models.deletion.CASCADE,
            ),
        ),
        migrations.AlterModelOptions(
            name="mandate", options={"ordering": [
                "scope_type", "space__name", "group__name", "activity__title",
                "project__title", "dossier__title", "profile__email", "role__name",
            ]},
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
                    | Q(scope_type="project", is_system=True, organization__isnull=True)
                    | Q(scope_type="dossier", is_system=True, organization__isnull=True)
                ), name="auth_role_scope_organization_valid",
            ),
        ),
        migrations.RemoveConstraint(model_name="mandate", name="auth_mandate_scope_target_valid"),
        migrations.AddConstraint(
            model_name="mandate",
            constraint=models.CheckConstraint(
                condition=(
                    Q(scope_type="platform", space__isnull=True, group__isnull=True, activity__isnull=True, dossier__isnull=True, project__isnull=True)
                    | Q(scope_type="space", space__isnull=False, group__isnull=True, activity__isnull=True, dossier__isnull=True, project__isnull=True)
                    | Q(scope_type="group", space__isnull=True, group__isnull=False, activity__isnull=True, dossier__isnull=True, project__isnull=True)
                    | Q(scope_type="activity", space__isnull=True, group__isnull=True, activity__isnull=False, dossier__isnull=True, project__isnull=True)
                    | Q(scope_type="dossier", space__isnull=True, group__isnull=True, activity__isnull=True, dossier__isnull=False, project__isnull=True)
                    | Q(scope_type="project", space__isnull=True, group__isnull=True, activity__isnull=True, dossier__isnull=True, project__isnull=False)
                ), name="auth_mandate_scope_target_valid",
            ),
        ),
        migrations.AddConstraint(
            model_name="mandate",
            constraint=models.UniqueConstraint(
                fields=("profile", "role", "scope_type", "project"),
                condition=Q(scope_type="project", status="active"),
                name="auth_mandate_active_project_unique",
            ),
        ),
        migrations.AddIndex(
            model_name="mandate",
            index=models.Index(fields=["project", "status"], name="auth_mand_proj_status_idx"),
        ),
        migrations.RunPython(seed_project_authority, reverse_project_authority),
    ]
