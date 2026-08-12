import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.db.models import Q


NAMESPACE = uuid.UUID("824d3be0-0cec-4d4f-b1ba-21dfb98678f6")


def stable_uuid(kind, code):
    return uuid.uuid5(NAMESPACE, f"{kind}:{code}")


def seed_group_authority(apps, schema_editor):
    Permission = apps.get_model("authorization", "Permission")
    Role = apps.get_model("authorization", "Role")
    RolePermission = apps.get_model("authorization", "RolePermission")

    permissions = {
        "space.groups.view": ("Voir les Groupes d’un Espace", "groups", "space"),
        "space.groups.manage": ("Gérer les Groupes d’un Espace", "groups", "space"),
        "group.view": ("Voir le Groupe", "groups", "group"),
        "group.manage": ("Gérer les informations du Groupe", "groups", "group"),
        "group.members.view": ("Voir les membres du Groupe", "groups", "group"),
        "group.members.manage": ("Gérer les membres du Groupe", "groups", "group"),
        "group.invitations.manage": ("Gérer les invitations du Groupe", "groups", "group"),
        "group.snapshots.create": ("Créer des snapshots du Groupe", "groups", "group"),
        "group.ownership.manage": ("Transférer la propriété du Groupe", "groups", "group"),
    }
    permission_objects = {}
    for code, (name, domain, scope_type) in permissions.items():
        permission, _ = Permission.objects.update_or_create(
            code=code,
            defaults={
                "id": stable_uuid("permission", code),
                "name": name,
                "description": "Permission système Makolo pour les Groupes.",
                "domain": domain,
                "scope_type": scope_type,
                "is_system": True,
                "is_active": True,
            },
        )
        permission_objects[code] = permission

    role_specs = {
        "group-owner": (
            "Propriétaire du Groupe",
            "Autorité complète et transfert de propriété du Groupe.",
            [
                "group.view",
                "group.manage",
                "group.members.view",
                "group.members.manage",
                "group.invitations.manage",
                "group.snapshots.create",
                "group.ownership.manage",
            ],
        ),
        "group-admin": (
            "Administrateur du Groupe",
            "Administration du Groupe, de ses membres, invitations et snapshots sans transfert de propriété.",
            [
                "group.view",
                "group.manage",
                "group.members.view",
                "group.members.manage",
                "group.invitations.manage",
                "group.snapshots.create",
            ],
        ),
        "group-moderator": (
            "Modérateur du Groupe",
            "Gestion courante de l’appartenance sans administration générale ni propriété.",
            [
                "group.view",
                "group.members.view",
                "group.members.manage",
            ],
        ),
    }
    for code, (name, description, permission_codes) in role_specs.items():
        role, _ = Role.objects.update_or_create(
            code=code,
            is_system=True,
            defaults={
                "id": stable_uuid("role", code),
                "name": name,
                "description": description,
                "scope_type": "group",
                "organization_id": None,
                "is_active": True,
            },
        )
        for permission_code in permission_codes:
            RolePermission.objects.get_or_create(
                role=role,
                permission=permission_objects[permission_code],
                defaults={"id": stable_uuid("role-permission", f"{code}:{permission_code}")},
            )

    for role_code in ("space-owner", "space-admin"):
        role = Role.objects.filter(code=role_code, is_system=True).first()
        if not role:
            continue
        for permission_code in ("space.groups.view", "space.groups.manage"):
            RolePermission.objects.get_or_create(
                role=role,
                permission=permission_objects[permission_code],
                defaults={"id": stable_uuid("role-permission", f"{role_code}:{permission_code}")},
            )


def unseed_group_authority(apps, schema_editor):
    Role = apps.get_model("authorization", "Role")
    Permission = apps.get_model("authorization", "Permission")
    Role.objects.filter(code__in=["group-owner", "group-admin", "group-moderator"], is_system=True).delete()
    Permission.objects.filter(
        code__in=[
            "space.groups.view",
            "space.groups.manage",
            "group.view",
            "group.manage",
            "group.members.view",
            "group.members.manage",
            "group.invitations.manage",
            "group.snapshots.create",
            "group.ownership.manage",
        ]
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("authorization", "0002_seed_roles_and_backfill"),
        ("groups", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name="permission",
            name="scope_type",
            field=models.CharField(choices=[("platform", "Plateforme Makolo"), ("space", "Espace"), ("group", "Groupe")], max_length=16),
        ),
        migrations.AlterField(
            model_name="role",
            name="scope_type",
            field=models.CharField(choices=[("platform", "Plateforme Makolo"), ("space", "Espace"), ("group", "Groupe")], max_length=16),
        ),
        migrations.AlterField(
            model_name="mandate",
            name="scope_type",
            field=models.CharField(choices=[("platform", "Plateforme Makolo"), ("space", "Espace"), ("group", "Groupe")], max_length=16),
        ),
        migrations.AddField(
            model_name="mandate",
            name="group",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="authority_mandates", to="groups.group"),
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
                ),
                name="auth_role_scope_organization_valid",
            ),
        ),
        migrations.RemoveConstraint(model_name="mandate", name="auth_mandate_scope_space_valid"),
        migrations.AddConstraint(
            model_name="mandate",
            constraint=models.CheckConstraint(
                condition=(
                    Q(scope_type="platform", space__isnull=True, group__isnull=True)
                    | Q(scope_type="space", space__isnull=False, group__isnull=True)
                    | Q(scope_type="group", space__isnull=True, group__isnull=False)
                ),
                name="auth_mandate_scope_target_valid",
            ),
        ),
        migrations.AddConstraint(
            model_name="mandate",
            constraint=models.UniqueConstraint(fields=("profile", "role", "scope_type", "group"), condition=Q(scope_type="group", status="active"), name="auth_mandate_active_group_unique"),
        ),
        migrations.AddIndex(
            model_name="mandate",
            index=models.Index(fields=["group", "status"], name="auth_mandate_group_status_idx"),
        ),
        migrations.RunPython(seed_group_authority, unseed_group_authority),
    ]
