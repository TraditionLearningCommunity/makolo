import uuid

from django.db import migrations

NAMESPACE = uuid.UUID("6f1af65f-c31f-4ec7-b3f4-16e01b1644a8")

def stable_uuid(kind, code):
    return uuid.uuid5(NAMESPACE, f"{kind}:{code}")

PERMISSIONS = (
    ("platform.recognition.view", "Voir Recognition au niveau plateforme", "platform"),
    ("platform.recognition.policy.manage", "Configurer les brouillons de Policy Recognition", "platform"),
    ("platform.recognition.policy.publish", "Publier une Policy Recognition", "platform"),
    ("platform.recognition.economy.manage", "Configurer l’économie des crédits Recognition", "platform"),
    ("platform.recognition.achievements.manage", "Configurer les Achievements Recognition", "platform"),
    ("platform.recognition.audit.view", "Auditer Recognition", "platform"),
    ("space.recognition.view", "Voir les crédits privés de cet Espace", "space"),
    ("space.recognition.spend", "Utiliser les crédits de cet Espace", "space"),
)

ROLE_BUNDLES = {
    "makolo-platform-admin": {code for code, _, scope in PERMISSIONS if scope == "platform"},
    "space-owner": {"space.recognition.view", "space.recognition.spend"},
    "space-admin": {"space.recognition.view", "space.recognition.spend"},
    "finance": {"space.recognition.view", "space.recognition.spend"},
}

def seed(apps, schema_editor):
    Permission = apps.get_model("authorization", "Permission")
    Role = apps.get_model("authorization", "Role")
    RolePermission = apps.get_model("authorization", "RolePermission")
    permissions = {}
    for code, name, scope_type in PERMISSIONS:
        permission, _ = Permission.objects.get_or_create(code=code, defaults={"id": stable_uuid("permission", code)})
        permission.name = name; permission.description = "Permission système Recognition, versionnée par migration."
        permission.domain = "recognition"; permission.scope_type = scope_type; permission.is_system = True; permission.is_active = True; permission.save()
        permissions[code] = permission
    for role_code, codes in ROLE_BUNDLES.items():
        role = Role.objects.filter(code=role_code, is_system=True, is_active=True).first()
        if role is None: continue
        for code in codes:
            RolePermission.objects.get_or_create(role=role, permission=permissions[code], defaults={"id": stable_uuid("role-permission", f"{role_code}:{code}")})

class Migration(migrations.Migration):
    dependencies = [("authorization", "0017_conversation_permissions")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
