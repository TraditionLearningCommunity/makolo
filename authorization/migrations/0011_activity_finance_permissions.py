import uuid

from django.db import migrations


NAMESPACE = uuid.UUID("b4ad75cb-f74f-4fce-b921-64975216d0d2")


def stable_uuid(kind, code):
    return uuid.uuid5(NAMESPACE, f"{kind}:{code}")


def seed_activity_finance(apps, schema_editor):
    Permission = apps.get_model("authorization", "Permission")
    Role = apps.get_model("authorization", "Role")
    RolePermission = apps.get_model("authorization", "RolePermission")

    permissions = {}
    for code, name in (
        ("activity.finance.view", "Voir les paiements de cette activité"),
        ("activity.finance.manage", "Gérer les paiements de cette activité"),
    ):
        permission, _ = Permission.objects.get_or_create(
            code=code,
            defaults={"id": stable_uuid("permission", code)},
        )
        permission.name = name
        permission.description = "Permission financière Activity-scoped du cœur Payment Makolo."
        permission.domain = "finance"
        permission.scope_type = "activity"
        permission.is_system = True
        permission.is_active = True
        permission.save()
        permissions[code] = permission

    role_code = "activity-finance"
    role = Role.objects.filter(code=role_code, is_system=True).first()
    if role is None:
        role = Role(id=stable_uuid("role", role_code), code=role_code, is_system=True)
    role.name = "Responsable finance d’activité"
    role.description = "Délégation locale pour consulter et enregistrer les paiements d’une Activity."
    role.scope_type = "activity"
    role.organization_id = None
    role.is_active = True
    role.save()
    for permission in permissions.values():
        RolePermission.objects.get_or_create(
            role=role,
            permission=permission,
            defaults={"id": stable_uuid("role-permission", f"{role_code}:{permission.code}")},
        )


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [("authorization", "0010_scanner_operations_permissions")]
    operations = [migrations.RunPython(seed_activity_finance, noop)]
