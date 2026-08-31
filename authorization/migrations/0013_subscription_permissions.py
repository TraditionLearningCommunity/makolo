import uuid

from django.db import migrations


NAMESPACE = uuid.UUID("6f1af65f-c31f-4ec7-b3f4-16e01b1644a8")


def stable_uuid(kind, code):
    return uuid.uuid5(NAMESPACE, f"{kind}:{code}")


PERMISSIONS = (
    ("space.subscription.view", "Voir l'abonnement de cet Espace", "space"),
    ("space.subscription.manage", "Gérer l'abonnement de cet Espace", "space"),
    ("platform.subscriptions.catalog.view", "Voir le catalogue Subscription interne", "platform"),
    ("platform.subscriptions.catalog.manage", "Gérer le catalogue Subscription", "platform"),
    ("platform.subscriptions.view", "Voir les Subscriptions de la plateforme", "platform"),
    ("platform.subscriptions.manage", "Gérer les Subscriptions de la plateforme", "platform"),
    ("platform.subscriptions.grants.manage", "Gérer les Entitlement Grants", "platform"),
    ("platform.subscriptions.reviews.manage", "Effectuer les reviews Subscription", "platform"),
)

ROLE_BUNDLES = {
    "space-owner": {"space.subscription.view", "space.subscription.manage"},
    "space-admin": {"space.subscription.view"},
    "makolo-platform-admin": {
        "platform.subscriptions.catalog.view",
        "platform.subscriptions.catalog.manage",
        "platform.subscriptions.view",
        "platform.subscriptions.manage",
        "platform.subscriptions.grants.manage",
        "platform.subscriptions.reviews.manage",
    },
}


def seed_subscription_permissions(apps, schema_editor):
    Permission = apps.get_model("authorization", "Permission")
    Role = apps.get_model("authorization", "Role")
    RolePermission = apps.get_model("authorization", "RolePermission")

    permissions = {}
    for code, name, scope_type in PERMISSIONS:
        permission, _ = Permission.objects.get_or_create(
            code=code,
            defaults={"id": stable_uuid("permission", code)},
        )
        permission.name = name
        permission.description = "Permission système Makolo Subscription versionnée par migration."
        permission.domain = "subscriptions"
        permission.scope_type = scope_type
        permission.is_system = True
        permission.is_active = True
        permission.save()
        permissions[code] = permission

    for role_code, permission_codes in ROLE_BUNDLES.items():
        role = Role.objects.filter(code=role_code, is_system=True, is_active=True).first()
        if role is None:
            continue
        for code in sorted(permission_codes):
            RolePermission.objects.get_or_create(
                role=role,
                permission=permissions[code],
                defaults={"id": stable_uuid("role-permission", f"{role_code}:{code}")},
            )


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [("authorization", "0012_services_opportunity_permissions")]
    operations = [migrations.RunPython(seed_subscription_permissions, noop)]
