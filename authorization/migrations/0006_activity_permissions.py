import uuid

from django.db import migrations


NAMESPACE = uuid.UUID("9e33a3d4-28d9-4f19-b596-55d572df95e0")


def stable_uuid(kind, code):
    return uuid.uuid5(NAMESPACE, f"{kind}:{code}")


def migrate_activity_permissions(apps, schema_editor):
    Permission = apps.get_model("authorization", "Permission")
    RolePermission = apps.get_model("authorization", "RolePermission")
    old_manage = Permission.objects.filter(code="activity.manage").first()
    role_ids = []
    if old_manage:
        role_ids = list(
            RolePermission.objects.filter(permission=old_manage, role__scope_type="space")
            .values_list("role_id", flat=True)
        )
    portfolio = {}
    for code, name in (
        ("space.activities.view", "Voir les activités d’un Espace"),
        ("space.activities.manage", "Gérer les activités d’un Espace"),
    ):
        permission, _ = Permission.objects.update_or_create(
            code=code,
            defaults={
                "id": stable_uuid("permission", code),
                "name": name,
                "description": "Permission portefeuille sur les Activities d’un Espace.",
                "domain": "activities",
                "scope_type": "space",
                "is_system": True,
                "is_active": True,
            },
        )
        portfolio[code] = permission
    for role_id in role_ids:
        RolePermission.objects.filter(role_id=role_id, permission=old_manage).delete()
        for code, permission in portfolio.items():
            RolePermission.objects.get_or_create(
                role_id=role_id,
                permission=permission,
                defaults={"id": stable_uuid("role-permission", f"{role_id}:{code}")},
            )
    if old_manage:
        old_manage.name = "Gérer cette activité"
        old_manage.description = "Permission locale sur une Activity précise."
        old_manage.domain = "activities"
        old_manage.scope_type = "activity"
        old_manage.is_system = True
        old_manage.is_active = True
        old_manage.save(update_fields=["name", "description", "domain", "scope_type", "is_system", "is_active", "updated_at"])
    else:
        old_manage = Permission.objects.create(
            id=stable_uuid("permission", "activity.manage"), code="activity.manage",
            name="Gérer cette activité", description="Permission locale sur une Activity précise.",
            domain="activities", scope_type="activity", is_system=True, is_active=True,
        )
    Permission.objects.update_or_create(
        code="activity.view",
        defaults={
            "id": stable_uuid("permission", "activity.view"),
            "name": "Voir cette activité",
            "description": "Permission locale sur une Activity précise.",
            "domain": "activities",
            "scope_type": "activity",
            "is_system": True,
            "is_active": True,
        },
    )


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [("authorization", "0005_activity_scope")]
    operations = [migrations.RunPython(migrate_activity_permissions, noop)]
