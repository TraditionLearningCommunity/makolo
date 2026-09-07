import uuid

from django.db import migrations


NAMESPACE = uuid.UUID("6f1af65f-c31f-4ec7-b3f4-16e01b1644a8")


def stable_uuid(kind, code):
    return uuid.uuid5(NAMESPACE, f"{kind}:{code}")


PERMISSIONS = (
    ("space.action_network.view", "Voir le réseau d’action géré par cet Espace", "space"),
    ("space.action_network.manage", "Gérer les besoins, propositions et disponibilités réseau de cet Espace", "space"),
    ("activity.action_network.view", "Voir le réseau d’action de cette Activity", "activity"),
    ("activity.action_network.manage", "Gérer les besoins, propositions et implications de cette Activity", "activity"),
)

ROLE_BUNDLES = {
    "space-owner": {"space.action_network.view", "space.action_network.manage"},
    "space-admin": {"space.action_network.view", "space.action_network.manage"},
    "activity-manager": {"activity.action_network.view", "activity.action_network.manage"},
}


def seed_action_network_permissions(apps, schema_editor):
    Permission = apps.get_model("authorization", "Permission")
    Role = apps.get_model("authorization", "Role")
    RolePermission = apps.get_model("authorization", "RolePermission")
    permissions = {}
    for code, name, scope_type in PERMISSIONS:
        permission, _ = Permission.objects.get_or_create(
            code=code,
            defaults={"id": stable_uuid("permission", code)},
        )
        permission.name = name
        permission.description = "Permission système Makolo du réseau d’action, versionnée par migration."
        permission.domain = "action_network"
        permission.scope_type = scope_type
        permission.is_system = True
        permission.is_active = True
        permission.save()
        permissions[code] = permission

    for role_code, permission_codes in ROLE_BUNDLES.items():
        role = Role.objects.filter(code=role_code, is_system=True, is_active=True).first()
        if role is None:
            continue
        for code in permission_codes:
            RolePermission.objects.get_or_create(
                role=role,
                permission=permissions[code],
                defaults={"id": stable_uuid("role-permission", f"{role_code}:{code}")},
            )


class Migration(migrations.Migration):
    dependencies = [("authorization", "0015_dossier_scope")]
    operations = [migrations.RunPython(seed_action_network_permissions, migrations.RunPython.noop)]
