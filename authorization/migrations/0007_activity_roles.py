import uuid

from django.db import migrations


NAMESPACE = uuid.UUID("f2503c5e-99fb-42fb-9ad7-daf9f0a70b09")


def stable_uuid(kind, code):
    return uuid.uuid5(NAMESPACE, f"{kind}:{code}")


def migrate_activity_roles(apps, schema_editor):
    Permission = apps.get_model("authorization", "Permission")
    Role = apps.get_model("authorization", "Role")
    RolePermission = apps.get_model("authorization", "RolePermission")

    historical = Role.objects.filter(code="activity-manager", scope_type="space", is_system=True).first()
    if historical:
        historical.code = "space-activity-manager"
        historical.name = "Responsable des activités"
        historical.description = "Pilotage du portefeuille d’activités de l’Espace."
        historical.save()

    portfolio_permissions = Permission.objects.filter(
        code__in=("space.activities.view", "space.activities.manage")
    )
    for role in Role.objects.filter(
        code__in=("space-owner", "space-admin", "space-activity-manager"),
        scope_type="space",
        is_system=True,
    ):
        for permission in portfolio_permissions:
            RolePermission.objects.get_or_create(role=role, permission=permission)

    local_role, _ = Role.objects.get_or_create(
        code="activity-manager",
        scope_type="activity",
        is_system=True,
        defaults={
            "id": stable_uuid("role", "activity-manager"),
            "name": "Responsable de l’activité",
            "description": "Autorité limitée à une Activity précise.",
            "organization_id": None,
            "is_active": True,
        },
    )
    local_role.name = "Responsable de l’activité"
    local_role.description = "Autorité limitée à une Activity précise."
    local_role.organization_id = None
    local_role.is_active = True
    local_role.save()
    for permission in Permission.objects.filter(code__in=("activity.view", "activity.manage")):
        RolePermission.objects.get_or_create(role=local_role, permission=permission)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [("authorization", "0006_activity_permissions")]
    operations = [migrations.RunPython(migrate_activity_roles, noop)]
