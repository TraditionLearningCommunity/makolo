import uuid

from django.db import migrations


NAMESPACE = uuid.UUID("b4ad75cb-f74f-4fce-b921-64975216d0d2")


def stable_uuid(kind, code):
    return uuid.uuid5(NAMESPACE, f"{kind}:{code}")


SERVICE_PERMISSIONS = (
    ("activity.services.configure", "Configurer les Services de cette activité"),
    ("activity.services.cases.view_all", "Voir tous les dossiers Services de cette activité"),
    ("activity.services.cases.view_assigned", "Voir les dossiers Services assignés de cette activité"),
    ("activity.services.cases.manage", "Gérer les dossiers Services de cette activité"),
    ("activity.services.assignments.manage", "Gérer les affectations Services de cette activité"),
    ("activity.services.steps.manage", "Gérer les étapes Services de cette activité"),
    ("activity.services.blockers.manage", "Gérer les blockers Services de cette activité"),
    ("activity.services.artifacts.view", "Voir les documents Services de cette activité"),
    ("activity.services.artifacts.manage", "Gérer les documents Services de cette activité"),
    ("activity.services.artifacts.restricted_view", "Voir les documents Services restreints de cette activité"),
    ("activity.services.reviews.manage", "Gérer les revues Services de cette activité"),
    ("activity.services.notes.internal", "Voir et écrire les notes internes Services de cette activité"),
    ("activity.services.outcomes.manage", "Gérer les soumissions et résultats Services de cette activité"),
    ("activity.services.payment_evidence.verify", "Vérifier les preuves de paiement Services de cette activité"),
)

OPPORTUNITY_PERMISSIONS = (
    ("opportunities.manage", "Gérer les Opportunities"),
    ("opportunities.review_submissions", "Revoir les propositions d'Opportunity"),
    ("opportunities.sources.verify", "Vérifier les sources d'Opportunity"),
    ("opportunities.merge", "Fusionner les Opportunities"),
)

ROLE_BUNDLES = {
    "activity-service-manager": (
        "Service Manager",
        "activity",
        {
            "activity.services.configure",
            "activity.services.cases.view_all",
            "activity.services.cases.manage",
            "activity.services.assignments.manage",
            "activity.services.steps.manage",
            "activity.services.blockers.manage",
            "activity.services.artifacts.view",
            "activity.services.artifacts.manage",
            "activity.services.reviews.manage",
            "activity.services.notes.internal",
            "activity.services.outcomes.manage",
            "activity.services.payment_evidence.verify",
        },
    ),
    "activity-service-facilitator": (
        "Service Facilitator",
        "activity",
        {
            "activity.services.cases.view_assigned",
            "activity.services.cases.manage",
            "activity.services.steps.manage",
            "activity.services.blockers.manage",
            "activity.services.artifacts.view",
            "activity.services.artifacts.manage",
            "activity.services.reviews.manage",
            "activity.services.notes.internal",
            "activity.services.outcomes.manage",
        },
    ),
    "activity-service-reviewer": (
        "Service Reviewer",
        "activity",
        {
            "activity.services.cases.view_assigned",
            "activity.services.artifacts.view",
            "activity.services.artifacts.restricted_view",
            "activity.services.reviews.manage",
        },
    ),
    "opportunity-curator": (
        "Opportunity Curator",
        "platform",
        {
            "opportunities.manage",
            "opportunities.review_submissions",
            "opportunities.sources.verify",
            "opportunities.merge",
        },
    ),
}


def seed_t34b_authorization(apps, schema_editor):
    Permission = apps.get_model("authorization", "Permission")
    Role = apps.get_model("authorization", "Role")
    RolePermission = apps.get_model("authorization", "RolePermission")

    permissions = {}
    for code, name in SERVICE_PERMISSIONS:
        permission, _ = Permission.objects.get_or_create(code=code, defaults={"id": stable_uuid("permission", code)})
        permission.name = name
        permission.description = "Permission Activity-scoped dédiée aux dossiers privés Makolo Services."
        permission.domain = "services"
        permission.scope_type = "activity"
        permission.is_system = True
        permission.is_active = True
        permission.save()
        permissions[code] = permission

    for code, name in OPPORTUNITY_PERMISSIONS:
        permission, _ = Permission.objects.get_or_create(code=code, defaults={"id": stable_uuid("permission", code)})
        permission.name = name
        permission.description = "Permission Platform-scoped dédiée à la curation des Opportunities Makolo."
        permission.domain = "opportunities"
        permission.scope_type = "platform"
        permission.is_system = True
        permission.is_active = True
        permission.save()
        permissions[code] = permission

    for role_code, (name, scope_type, bundle) in ROLE_BUNDLES.items():
        role = Role.objects.filter(code=role_code, is_system=True).first()
        if role is None:
            role = Role(id=stable_uuid("role", role_code), code=role_code, is_system=True)
        role.name = name
        role.description = "Rôle système Makolo Services." if scope_type == "activity" else "Rôle système de curation Opportunity."
        role.scope_type = scope_type
        role.organization_id = None
        role.is_active = True
        role.save()
        RolePermission.objects.filter(role=role).exclude(permission__code__in=bundle).delete()
        for code in sorted(bundle):
            RolePermission.objects.get_or_create(
                role=role,
                permission=permissions[code],
                defaults={"id": stable_uuid("role-permission", f"{role_code}:{code}")},
            )


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [("authorization", "0011_activity_finance_permissions")]
    operations = [migrations.RunPython(seed_t34b_authorization, noop)]
