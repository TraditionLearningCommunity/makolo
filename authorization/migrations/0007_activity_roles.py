import uuid

from django.db import migrations


NAMESPACE = uuid.UUID("f2503c5e-99fb-42fb-9ad7-daf9f0a70b09")


def stable_uuid(kind, code):
    return uuid.uuid5(NAMESPACE, f"{kind}:{code}")


def migrate_activity_roles(apps, schema_editor):
    Permission = apps.get_model("authorization", "Permission")
    Role = apps.get_model("authorization", "Role")
    RolePermission = apps.get_model("authorization", "RolePermission")
    portfolio = {
        code: Permission.objects.get(code=code)
        for code in ("space.activities.view", "space.activities.manage")
    }
    historical = Role.objects.filter(code="activity-manager", scope_type="space", is_system=True).first()
    if historical:
        historical.code = "space-activity-manager"
        historical.name = "Responsable des activités"
        historical.description = "Pilotage du portefeuille d’activités et capacités opérationnelles historiques de l’Espace."
        historical.save(update_fields=["code", "name", "description", "updated_at"])
    for role_code in ("space-owner", "space-admin", "space-activity-manager"):
        role = Role.objects.filter(code=role_code, scope_type="space", is_system=True).first()
        if role:
            for code, permission in portfolio.items():
                RolePermission.objects.get_or_create(
                    role=role,
                    permission=permission,
                    defaults={"id": stable_uuid("role-permission", f"{role_code}:{code}")},
                )
    local_role, _ = Role.objects.update_or_create(
        code="activity-manager",
        is_system=True,
        defaults={
            "id": stable_uuid("role", "activity-manager"),
            "name": "Responsable de l’activité",
            "description": "Autorité limitée à une Activity précise.",
            "scope_type": "activity",
            "organization_id": None,
            "is_active": True,
        },
    )
    for code in ("activity.view", "activity.manage"):
        permission = Permission.objects.get(code=code)
        RolePermission.objects.get_or_create(
            role=local_role,
            permission=permission,
            defaults={"id": stable_uuid("role-permission", f"activity-manager:{code}")},
        )


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [("authorization", "0006_activity_permissions")]
    operations = [migrations.RunPython(migrate_activity_roles, noop)]
