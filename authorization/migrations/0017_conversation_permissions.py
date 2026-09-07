import uuid

from django.db import migrations


NAMESPACE = uuid.UUID("6f1af65f-c31f-4ec7-b3f4-16e01b1644a8")


def stable_uuid(kind, code):
    return uuid.uuid5(NAMESPACE, f"{kind}:{code}")


PERMISSIONS = (
    ("space.conversations.publish", "Publier dans les Conversations de cet Espace", "space"),
    ("space.conversations.moderate", "Modérer les Conversations de cet Espace", "space"),
    ("space.conversations.manage", "Gérer les Conversations de cet Espace", "space"),
    ("space.conversations.routes.manage", "Gérer les routes externes des Conversations de cet Espace", "space"),
    ("group.conversations.publish", "Publier dans les Conversations de ce Groupe", "group"),
    ("group.conversations.moderate", "Modérer les Conversations de ce Groupe", "group"),
    ("group.conversations.manage", "Gérer les Conversations de ce Groupe", "group"),
    ("group.conversations.routes.manage", "Gérer les routes externes des Conversations de ce Groupe", "group"),
    ("activity.conversations.publish", "Publier dans les Conversations de cette Activity", "activity"),
    ("activity.conversations.moderate", "Modérer les Conversations de cette Activity", "activity"),
    ("activity.conversations.manage", "Gérer les Conversations de cette Activity", "activity"),
    ("activity.conversations.routes.manage", "Gérer les routes externes des Conversations de cette Activity", "activity"),
    ("dossier.conversations.publish", "Publier dans les Conversations de ce Dossier", "dossier"),
    ("dossier.conversations.moderate", "Modérer les Conversations de ce Dossier", "dossier"),
    ("dossier.conversations.manage", "Gérer les Conversations de ce Dossier", "dossier"),
    ("dossier.conversations.routes.manage", "Gérer les routes externes des Conversations de ce Dossier", "dossier"),
)

ROLE_DEFINITIONS = {
    "space-communication-manager": ("Responsable communication", "space"),
    "group-communication-manager": ("Responsable communication", "group"),
    "activity-communication-manager": ("Responsable communication", "activity"),
    "dossier-communication-manager": ("Responsable communication", "dossier"),
}

ROLE_BUNDLES = {
    "space-owner": {code for code, _, scope in PERMISSIONS if scope == "space"},
    "space-admin": {code for code, _, scope in PERMISSIONS if scope == "space"},
    "space-communication-manager": {code for code, _, scope in PERMISSIONS if scope == "space"},
    "group-owner": {code for code, _, scope in PERMISSIONS if scope == "group"},
    "group-admin": {code for code, _, scope in PERMISSIONS if scope == "group"},
    "group-moderator": {"group.conversations.publish", "group.conversations.moderate"},
    "group-communication-manager": {code for code, _, scope in PERMISSIONS if scope == "group"},
    "activity-manager": {code for code, _, scope in PERMISSIONS if scope == "activity"},
    "activity-communication-manager": {code for code, _, scope in PERMISSIONS if scope == "activity"},
    "dossier-manager": {code for code, _, scope in PERMISSIONS if scope == "dossier"},
    "dossier-admin": {code for code, _, scope in PERMISSIONS if scope == "dossier"},
    "dossier-communication-manager": {code for code, _, scope in PERMISSIONS if scope == "dossier"},
}


def seed_conversation_permissions(apps, schema_editor):
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
        permission.description = "Permission système Makolo des Conversations d’action, versionnée par migration."
        permission.domain = "conversations"
        permission.scope_type = scope_type
        permission.is_system = True
        permission.is_active = True
        permission.save()
        permissions[code] = permission

    for role_code, (name, scope_type) in ROLE_DEFINITIONS.items():
        role, _ = Role.objects.get_or_create(
            code=role_code,
            is_system=True,
            defaults={
                "id": stable_uuid("role", role_code),
                "name": name,
                "description": "Responsabilité de communication sans transfert d’autorité métier hors Conversations.",
                "scope_type": scope_type,
                "organization_id": None,
                "is_active": True,
            },
        )
        role.name = name
        role.description = "Responsabilité de communication sans transfert d’autorité métier hors Conversations."
        role.scope_type = scope_type
        role.organization_id = None
        role.is_active = True
        role.save()

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
    dependencies = [("authorization", "0016_action_network_permissions")]
    operations = [migrations.RunPython(seed_conversation_permissions, migrations.RunPython.noop)]
