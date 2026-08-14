import uuid

from django.db import migrations


NAMESPACE = uuid.UUID("c1c84458-ae9d-46d0-b4d4-b5ae73e9d8a7")


def stable_uuid(kind, code):
    return uuid.uuid5(NAMESPACE, f"{kind}:{code}")


def seed_commerce_capacity_permissions(apps, schema_editor):
    Permission = apps.get_model("authorization", "Permission")
    Role = apps.get_model("authorization", "Role")
    RolePermission = apps.get_model("authorization", "RolePermission")

    definitions = (
        ("activity.commerce.view", "Voir le commerce de cette activité", "commerce"),
        ("activity.commerce.manage", "Gérer les tarifs et commandes de cette activité", "commerce"),
        ("activity.capacity.view", "Voir la capacité de cette activité", "capacity"),
        ("activity.capacity.manage", "Gérer la capacité de cette activité", "capacity"),
    )
    permissions = []
    for code, name, domain in definitions:
        permission, _ = Permission.objects.get_or_create(code=code, defaults={"id": stable_uuid("permission", code)})
        permission.name = name
        permission.description = "Permission Activity-scoped du cœur Commerce/Capacity Makolo."
        permission.domain = domain
        permission.scope_type = "activity"
        permission.is_system = True
        permission.is_active = True
        permission.save()
        permissions.append(permission)

    local_manager = Role.objects.filter(code="activity-manager", scope_type="activity", is_system=True, is_active=True).first()
    if local_manager:
        for permission in permissions:
            RolePermission.objects.get_or_create(role=local_manager, permission=permission)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [("authorization", "0008_journey_access_permissions")]
    operations = [migrations.RunPython(seed_commerce_capacity_permissions, noop)]
