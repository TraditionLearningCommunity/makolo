import uuid

from django.db import migrations


NAMESPACE = uuid.UUID("1a2bc1d0-e455-4f7f-bd0f-8d1cbda97b08")


def stable_uuid(kind, code):
    return uuid.uuid5(NAMESPACE, f"{kind}:{code}")


def seed_permissions(apps, schema_editor):
    Permission = apps.get_model("authorization", "Permission")
    Role = apps.get_model("authorization", "Role")
    RolePermission = apps.get_model("authorization", "RolePermission")

    definitions = (
        ("activity.access.scan", "Contrôler les Accès de cette activité", "access"),
        ("activity.operations.view", "Voir les incidents de cette activité", "operations"),
        ("activity.operations.manage", "Gérer les incidents de cette activité", "operations"),
    )
    permissions = {}
    for code, name, domain in definitions:
        permission, _ = Permission.objects.get_or_create(
            code=code,
            defaults={"id": stable_uuid("permission", code)},
        )
        permission.name = name
        permission.description = "Permission Activity-scoped versionnée pour Scanner/Operations Makolo."
        permission.domain = domain
        permission.scope_type = "activity"
        permission.is_system = True
        permission.is_active = True
        permission.save()
        permissions[code] = permission

    role_definitions = {
        "activity-scanner": (
            "Agent de contrôle d’accès",
            "Délégation Activity minimale pour contrôler les Accès sans administration métier.",
            ["activity.access.scan"],
        ),
        "activity-operations-manager": (
            "Responsable Operations d’activité",
            "Gestion locale des incidents Operations d’une Activity sans privilèges Finance ou Commerce.",
            ["activity.operations.view", "activity.operations.manage"],
        ),
    }
    for code, (name, description, permission_codes) in role_definitions.items():
        role = Role.objects.filter(code=code, is_system=True).first()
        if role is None:
            role = Role(id=stable_uuid("role", code), code=code, is_system=True)
        role.name = name
        role.description = description
        role.scope_type = "activity"
        role.organization_id = None
        role.is_active = True
        role.save()
        for permission_code in permission_codes:
            RolePermission.objects.get_or_create(
                role=role,
                permission=permissions[permission_code],
                defaults={"id": stable_uuid("role-permission", f"{code}:{permission_code}")},
            )

    # Existing local Activity managers already administer Access; scanning is a
    # narrower capability they should also possess explicitly.
    local_manager = Role.objects.filter(
        code="activity-manager",
        scope_type="activity",
        is_system=True,
        is_active=True,
    ).first()
    if local_manager:
        RolePermission.objects.get_or_create(
            role=local_manager,
            permission=permissions["activity.access.scan"],
        )


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [("authorization", "0009_commerce_capacity_permissions")]
    operations = [migrations.RunPython(seed_permissions, noop)]
