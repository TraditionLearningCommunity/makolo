import uuid

from django.db import migrations
from django.utils import timezone


NAMESPACE = uuid.UUID("9a1f6f3e-b0a1-4a7e-ae86-4a9c5c0e8f24")


def stable_uuid(value):
    return uuid.uuid5(NAMESPACE, str(value))


PERMISSIONS = [
    ("platform.manage", "Administrer les capacités métier Makolo", "platform", "platform"),
    ("space.view", "Accéder à un Espace", "spaces", "space"),
    ("space.manage", "Gérer un Espace", "spaces", "space"),
    ("space.team.manage", "Gérer l'équipe d'un Espace", "spaces", "space"),
    ("space.ownership.manage", "Gérer la propriété d'un Espace", "spaces", "space"),
    ("space.activities.view", "Voir les activités d'un Espace", "activities", "space"),
    ("space.activities.manage", "Gérer les activités d'un Espace", "activities", "space"),
    ("orders.view", "Voir les commandes opérationnelles", "commerce", "space"),
    ("tickets.view", "Voir les droits/billets opérationnels", "access", "space"),
    ("finance.view", "Voir les données financières", "finance", "space"),
    ("finance.manage", "Gérer paiements et remboursements", "finance", "space"),
    ("marketing.manage", "Gérer marketing et communication", "marketing", "space"),
    ("access.manage", "Gérer le contrôle d'accès", "access", "space"),
    ("crm.view", "Voir le CRM", "crm", "space"),
    ("crm.manage", "Gérer le CRM", "crm", "space"),
    ("crm.financials.view", "Voir les données financières Customer 360", "crm", "space"),
    ("promotions.view", "Voir les promotions", "promotions", "space"),
    ("promotions.manage", "Gérer les promotions", "promotions", "space"),
    ("promotions.financials.view", "Voir les redemptions financières", "promotions", "space"),
    ("loyalty.view", "Voir l'espace fidélité", "loyalty", "space"),
    ("loyalty.manage", "Gérer la stratégie fidélité", "loyalty", "space"),
    ("loyalty.finance", "Gérer les opérations financières fidélité", "loyalty", "space"),
    ("partners.manage", "Gérer partenaires et acquisition", "partners", "space"),
    ("partners.finance", "Gérer les finances partenaires", "partners", "space"),
    ("analytics.view", "Voir les analytics opérationnelles", "analytics", "space"),
    ("analytics.growth.view", "Voir les analytics growth", "analytics", "space"),
    ("analytics.financials.view", "Voir les analytics financières", "analytics", "space"),
    ("growth.feedback.view", "Voir les retours privés Growth", "growth", "space"),
]


SPACE_PERMISSION_CODES = [code for code, _name, _domain, scope in PERMISSIONS if scope == "space"]
ADMIN_PERMISSION_CODES = [code for code in SPACE_PERMISSION_CODES if code != "space.ownership.manage"]

ROLE_DEFINITIONS = {
    "makolo-platform-admin": {
        "name": "Administrateur Makolo",
        "description": "Autorité métier transversale sur la plateforme Makolo.",
        "scope": "platform",
        "permissions": ["platform.manage"],
    },
    "space-owner": {
        "name": "Propriétaire d'Espace",
        "description": "Responsabilité complète sur un Espace, y compris sa propriété et son équipe.",
        "scope": "space",
        "permissions": SPACE_PERMISSION_CODES,
    },
    "space-admin": {
        "name": "Administrateur d'Espace",
        "description": "Administration opérationnelle complète sans pouvoir transférer la propriété.",
        "scope": "space",
        "permissions": ADMIN_PERMISSION_CODES,
    },
    "space-activity-manager": {
        "name": "Responsable des activités",
        "description": "Pilotage des activités, commandes opérationnelles et accès sans finances.",
        "scope": "space",
        "permissions": [
            "space.view", "space.activities.view", "space.activities.manage", "orders.view", "tickets.view", "access.manage",
            "crm.view", "promotions.view", "analytics.view", "analytics.growth.view",
            "growth.feedback.view",
        ],
    },
    "finance": {
        "name": "Finance",
        "description": "Paiements, remboursements et lectures financières sans marketing/CRM.",
        "scope": "space",
        "permissions": [
            "space.view", "orders.view", "finance.view", "finance.manage", "promotions.view",
            "promotions.financials.view", "loyalty.view", "loyalty.finance", "partners.finance",
            "analytics.view", "analytics.growth.view", "analytics.financials.view",
        ],
    },
    "marketing": {
        "name": "Marketing / Communication",
        "description": "CRM, acquisition, promotions et fidélité sans données financières privées.",
        "scope": "space",
        "permissions": [
            "space.view", "marketing.manage", "crm.view", "crm.manage", "promotions.view",
            "promotions.manage", "loyalty.view", "loyalty.manage", "partners.manage",
            "analytics.view", "analytics.growth.view", "growth.feedback.view",
        ],
    },
    "access-manager": {
        "name": "Responsable accès",
        "description": "Contrôle d'accès et données de titulaire nécessaires à cette mission.",
        "scope": "space",
        "permissions": ["space.view", "tickets.view", "access.manage", "analytics.view"],
    },
}

LEGACY_ROLE_MAP = {
    "owner": "space-owner",
    "admin": "space-admin",
    "event_manager": "space-activity-manager",
    "finance": "finance",
    "marketing": "marketing",
    "scanner_manager": "access-manager",
}


def seed_and_backfill(apps, schema_editor):
    Permission = apps.get_model("authorization", "Permission")
    Role = apps.get_model("authorization", "Role")
    RolePermission = apps.get_model("authorization", "RolePermission")
    Mandate = apps.get_model("authorization", "Mandate")
    Organization = apps.get_model("organizations", "Organization")
    OrganizationMembership = apps.get_model("organizations", "OrganizationMembership")
    Team = apps.get_model("organizations", "Team")
    TeamMembership = apps.get_model("organizations", "TeamMembership")
    User = apps.get_model("accounts", "User")

    permission_by_code = {}
    for code, name, domain, scope_type in PERMISSIONS:
        permission, _ = Permission.objects.update_or_create(
            code=code,
            defaults={
                "name": name,
                "description": "Permission système Makolo versionnée par migration.",
                "domain": domain,
                "scope_type": scope_type,
                "is_system": True,
                "is_active": True,
            },
        )
        permission_by_code[code] = permission

    role_by_code = {}
    for code, definition in ROLE_DEFINITIONS.items():
        role, _ = Role.objects.update_or_create(
            id=stable_uuid(f"role:{code}"),
            defaults={
                "code": code,
                "name": definition["name"],
                "description": definition["description"],
                "scope_type": definition["scope"],
                "organization_id": None,
                "is_system": True,
                "is_active": True,
            },
        )
        role_by_code[code] = role
        for permission_code in definition["permissions"]:
            permission = permission_by_code[permission_code]
            RolePermission.objects.update_or_create(
                id=stable_uuid(f"role-permission:{code}:{permission_code}"),
                defaults={"role_id": role.pk, "permission_id": permission.pk},
            )

    now = timezone.now()
    for organization in Organization.objects.all().iterator():
        team, _ = Team.objects.update_or_create(
            id=stable_uuid(f"team:{organization.pk}"),
            defaults={
                "organization_id": organization.pk,
                "name": "Équipe principale",
                "is_default": True,
                "is_active": True,
            },
        )
        memberships = OrganizationMembership.objects.filter(organization_id=organization.pk)
        for membership in memberships.iterator():
            status = "active" if membership.is_active else "inactive"
            TeamMembership.objects.update_or_create(
                id=stable_uuid(f"team-membership:{membership.pk}"),
                defaults={
                    "team_id": team.pk,
                    "user_id": membership.user_id,
                    "status": status,
                    "invited_by_id": membership.invited_by_id,
                    "joined_at": membership.joined_at,
                },
            )
            if not membership.is_active:
                continue
            role_code = LEGACY_ROLE_MAP.get(membership.role)
            if not role_code:
                continue
            role = role_by_code[role_code]
            Mandate.objects.update_or_create(
                id=stable_uuid(f"space-mandate:{membership.pk}:{role_code}"),
                defaults={
                    "profile_id": membership.user_id,
                    "role_id": role.pk,
                    "scope_type": "space",
                    "space_id": organization.pk,
                    "status": "active",
                    "valid_from": None,
                    "valid_until": None,
                    "granted_by_id": membership.invited_by_id or organization.created_by_id,
                    "granted_at": membership.joined_at or now,
                    "revoked_at": None,
                    "source": "organization-membership-backfill",
                },
            )

    platform_role = role_by_code["makolo-platform-admin"]
    for user in User.objects.filter(is_staff=True).iterator():
        Mandate.objects.update_or_create(
            id=stable_uuid(f"platform-admin:{user.pk}"),
            defaults={
                "profile_id": user.pk,
                "role_id": platform_role.pk,
                "scope_type": "platform",
                "space_id": None,
                "status": "active",
                "valid_from": None,
                "valid_until": None,
                "granted_by_id": None,
                "granted_at": now,
                "revoked_at": None,
                "source": "staff-backfill",
            },
        )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("authorization", "0001_initial"),
        ("organizations", "0003_team_teammembership"),
    ]
    operations = [migrations.RunPython(seed_and_backfill, noop_reverse)]
