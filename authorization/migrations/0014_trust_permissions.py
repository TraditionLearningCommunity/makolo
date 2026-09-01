import uuid

from django.db import migrations


NAMESPACE = uuid.UUID("6f1af65f-c31f-4ec7-b3f4-16e01b1644a8")


def stable_uuid(kind, code):
    return uuid.uuid5(NAMESPACE, f"{kind}:{code}")


PERMISSIONS = (
    ("space.trust.view", "Voir la qualité et les dossiers Trust autorisés de cet Espace", "space"),
    ("space.trust.manage", "Gérer les demandes et réponses Trust déléguées de cet Espace", "space"),
    ("platform.trust.review", "Examiner et décider les dossiers Trust Makolo", "platform"),
)

ROLE_BUNDLES = {
    "space-owner": {"space.trust.view", "space.trust.manage"},
    "space-admin": {"space.trust.view"},
    "makolo-platform-admin": {"platform.trust.review"},
}


def seed_trust_permissions(apps, schema_editor):
    Permission = apps.get_model("authorization", "Permission")
    Role = apps.get_model("authorization", "Role")
    RolePermission = apps.get_model("authorization", "RolePermission")
    permissions = {}
    for code, name, scope_type in PERMISSIONS:
        permission, _ = Permission.objects.get_or_create(code=code, defaults={"id": stable_uuid("permission", code)})
        permission.name = name
        permission.description = "Permission système Makolo Trust versionnée par migration."
        permission.domain = "trust"
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
            RolePermission.objects.get_or_create(role=role, permission=permissions[code], defaults={"id": stable_uuid("role-permission", f"{role_code}:{code}")})


class Migration(migrations.Migration):
    dependencies = [("authorization", "0013_subscription_permissions")]
    operations = [migrations.RunPython(seed_trust_permissions, migrations.RunPython.noop)]
