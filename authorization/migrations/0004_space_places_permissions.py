from django.db import migrations


PERMISSIONS = (
    ("space.places.view", "Voir les Lieux d'un Espace"),
    ("space.places.manage", "Gérer les Lieux d'un Espace"),
)


def seed_space_place_permissions(apps, schema_editor):
    Permission = apps.get_model("authorization", "Permission")
    Role = apps.get_model("authorization", "Role")
    RolePermission = apps.get_model("authorization", "RolePermission")
    for code, name in PERMISSIONS:
        permission, _ = Permission.objects.update_or_create(
            code=code,
            defaults={
                "name": name,
                "description": "Permission système Makolo pour les Lieux d'un Espace.",
                "domain": "spaces",
                "scope_type": "space",
                "is_system": True,
                "is_active": True,
            },
        )
        for role in Role.objects.filter(
            code__in=("space-owner", "space-admin"),
            is_system=True,
            scope_type="space",
        ):
            RolePermission.objects.get_or_create(role=role, permission=permission)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("authorization", "0003_group_scope"),
        ("geography", "0001_initial"),
    ]

    operations = [migrations.RunPython(seed_space_place_permissions, noop_reverse)]
