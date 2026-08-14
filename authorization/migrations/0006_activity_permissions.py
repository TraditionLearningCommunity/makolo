import uuid

from django.db import migrations


NAMESPACE = uuid.UUID("9e33a3d4-28d9-4f19-b596-55d572df95e0")


def stable_uuid(kind, code):
    return uuid.uuid5(NAMESPACE, f"{kind}:{code}")


def ensure_permission(Permission, *, code, name, scope_type):
    permission, _ = Permission.objects.get_or_create(
        code=code,
        defaults={"id": stable_uuid("permission", code)},
    )
    permission.name = name
    permission.description = "Permission système du noyau Activities Makolo."
    permission.domain = "activities"
    permission.scope_type = scope_type
    permission.is_system = True
    permission.is_active = True
    permission.save()
    return permission


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

    portfolio_view = ensure_permission(
        Permission, code="space.activities.view", name="Voir les activités d’un Espace", scope_type="space"
    )
    portfolio_manage = ensure_permission(
        Permission, code="space.activities.manage", name="Gérer les activités d’un Espace", scope_type="space"
    )
    for role_id in role_ids:
        RolePermission.objects.filter(role_id=role_id, permission=old_manage).delete()
        for permission in (portfolio_view, portfolio_manage):
            RolePermission.objects.get_or_create(role_id=role_id, permission=permission)

    local_manage = ensure_permission(
        Permission, code="activity.manage", name="Gérer cette activité", scope_type="activity"
    )
    ensure_permission(Permission, code="activity.view", name="Voir cette activité", scope_type="activity")
    RolePermission.objects.filter(permission=local_manage).exclude(role__scope_type="activity").delete()


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [("authorization", "0005_activity_scope")]
    operations = [migrations.RunPython(migrate_activity_permissions, noop)]
