from decimal import Decimal

from django.db import migrations


FEATURES = (
    {
        "code": "activities.create",
        "name": "Création d’activités",
        "description": "Capacité technique permettant au sujet de créer des Activity canoniques.",
        "domain": "activities",
        "value_type": "boolean",
        "unit": "",
        "supports_profile": True,
        "supports_space": True,
        "aggregation_strategy": "BOOLEAN_OR",
        "usage_provider": "",
        "enforcement_policy": "feature_gate",
        "minimum_value": None,
        "maximum_value": None,
        "enum_values": [],
        "is_active": True,
    },
    {
        "code": "team.members",
        "name": "Membres d’équipe actifs",
        "description": "Limite technique sur les TeamMembership actifs d’un Espace.",
        "domain": "organizations",
        "value_type": "integer",
        "unit": "member",
        "supports_profile": False,
        "supports_space": True,
        "aggregation_strategy": "SUM",
        "usage_provider": "organizations.active_team_members",
        "enforcement_policy": "preserve_existing_block_new",
        "minimum_value": Decimal("0"),
        "maximum_value": None,
        "enum_values": [],
        "is_active": True,
    },
    {
        "code": "custom_roles",
        "name": "Rôles personnalisés",
        "description": "Capacité technique pour les Role non système propres à un Espace.",
        "domain": "authorization",
        "value_type": "boolean",
        "unit": "",
        "supports_profile": False,
        "supports_space": True,
        "aggregation_strategy": "BOOLEAN_OR",
        "usage_provider": "",
        "enforcement_policy": "feature_gate",
        "minimum_value": None,
        "maximum_value": None,
        "enum_values": [],
        "is_active": True,
    },
)


def seed_features(apps, schema_editor):
    FeatureDefinition = apps.get_model("subscriptions", "FeatureDefinition")
    for feature in FEATURES:
        FeatureDefinition.objects.update_or_create(code=feature["code"], defaults=feature)


def unseed_features(apps, schema_editor):
    FeatureDefinition = apps.get_model("subscriptions", "FeatureDefinition")
    codes = [feature["code"] for feature in FEATURES]
    if not FeatureDefinition.objects.filter(code__in=codes, plan_entitlements__isnull=False).exists():
        FeatureDefinition.objects.filter(code__in=codes).delete()


class Migration(migrations.Migration):
    dependencies = [("subscriptions", "0001_initial")]
    operations = [migrations.RunPython(seed_features, unseed_features)]
