import uuid

from django.db import migrations


NAMESPACE = uuid.UUID("31cc2be0-cd65-46da-89d6-ec8ac50d1f4c")


def stable_uuid(kind, code):
    return uuid.uuid5(NAMESPACE, f"{kind}:{code}")


def seed_journey_access_permissions(apps, schema_editor):
    Permission = apps.get_model("authorization", "Permission")
    Role = apps.get_model("authorization", "Role")
    RolePermission = apps.get_model("authorization", "RolePermission")

    definitions = (
        ("activity.requests.view", "Voir les Demandes de cette activité", "journeys"),
        ("activity.requests.decide", "Décider les Demandes de cette activité", "journeys"),
        ("activity.access.view", "Voir les Accès de cette activité", "access"),
        ("activity.access.manage", "Gérer les Accès de cette activité", "access"),
    )
    permissions = []
    for code, name, domain in definitions:
        permission, _ = Permission.objects.get_or_create(
            code=code,
            defaults={"id": stable_uuid("permission", code)},
        )
        permission.name = name
        permission.description = "Permission Activity-scoped du cœur Démarche/Accès Makolo."
        permission.domain = domain
        permission.scope_type = "activity"
        permission.is_system = True
        permission.is_active = True
        permission.save()
        permissions.append(permission)

    local_manager = Role.objects.filter(
        code="activity-manager",
        scope_type="activity",
        is_system=True,
        is_active=True,
    ).first()
    if local_manager:
        for permission in permissions:
            RolePermission.objects.get_or_create(role=local_manager, permission=permission)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [("authorization", "0007_activity_roles")]
    operations = [migrations.RunPython(seed_journey_access_permissions, noop)]
