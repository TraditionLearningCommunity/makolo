from __future__ import annotations

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

from .contracts import (
    AcquisitionMode,
    CatalogVisibility,
    EntitlementAggregationStrategy,
    FeatureEnforcementPolicy,
    FeatureValueType,
    SubscriptionPlanType,
    SubscriptionSubjectType,
)
from .models import FeatureDefinition, PlanEntitlement, PlanVersion, SubscriptionPlan
from .services import publish_plan_version


FEATURE_DEFAULTS = {
    "activities.create": {
        "name": "Création d’activités",
        "description": "Capacité technique permettant au sujet de créer des Activity canoniques.",
        "domain": "activities",
        "value_type": FeatureValueType.BOOLEAN,
        "unit": "",
        "supports_profile": True,
        "supports_space": True,
        "aggregation_strategy": EntitlementAggregationStrategy.BOOLEAN_OR,
        "usage_provider": "",
        "enforcement_policy": FeatureEnforcementPolicy.FEATURE_GATE,
        "minimum_value": None,
        "maximum_value": None,
        "enum_values": [],
        "is_active": True,
    },
    "team.members": {
        "name": "Membres d’équipe actifs",
        "description": "Limite technique sur les TeamMembership actifs d’un Espace.",
        "domain": "organizations",
        "value_type": FeatureValueType.INTEGER,
        "unit": "member",
        "supports_profile": False,
        "supports_space": True,
        "aggregation_strategy": EntitlementAggregationStrategy.SUM,
        "usage_provider": "organizations.active_team_members",
        "enforcement_policy": FeatureEnforcementPolicy.PRESERVE_EXISTING_BLOCK_NEW,
        "minimum_value": Decimal("0"),
        "maximum_value": None,
        "enum_values": [],
        "is_active": True,
    },
    "custom_roles": {
        "name": "Rôles personnalisés",
        "description": "Capacité technique pour les Role non système propres à un Espace.",
        "domain": "authorization",
        "value_type": FeatureValueType.BOOLEAN,
        "unit": "",
        "supports_profile": False,
        "supports_space": True,
        "aggregation_strategy": EntitlementAggregationStrategy.BOOLEAN_OR,
        "usage_provider": "",
        "enforcement_policy": FeatureEnforcementPolicy.FEATURE_GATE,
        "minimum_value": None,
        "maximum_value": None,
        "enum_values": [],
        "is_active": True,
    },
}


BASE_DEFAULTS = {
    SubscriptionSubjectType.PROFILE: {
        "code": "profile.base",
        "name": "Makolo Base — Profil",
        "entitlements": {"activities.create": True},
    },
    SubscriptionSubjectType.SPACE: {
        "code": "space.base",
        "name": "Makolo Base — Espace",
        "entitlements": {"activities.create": True, "custom_roles": False},
    },
}


@transaction.atomic
def ensure_default_catalog():
    """Ensure the non-commercial universal BASE catalogue required by S2.

    This is also safe to run from ``post_migrate`` after Django test ``flush``.
    It never invents a paid tier or a quantitative team limit.
    """
    features = {}
    for code, defaults in FEATURE_DEFAULTS.items():
        feature, created = FeatureDefinition.objects.get_or_create(code=code, defaults=defaults)
        if not created:
            expected = {key: value for key, value in defaults.items() if key in FeatureDefinition.TECHNICAL_FIELDS}
            mismatches = [key for key, value in expected.items() if getattr(feature, key) != value]
            if mismatches:
                raise ValidationError(
                    f"La Feature {code} existe avec un contrat technique incompatible: {', '.join(mismatches)}."
                )
        features[code] = feature

    plans = {}
    for subject_type, definition in BASE_DEFAULTS.items():
        plan, created = SubscriptionPlan.objects.get_or_create(
            code=definition["code"],
            defaults={
                "plan_type": SubscriptionPlanType.BASE,
                "subject_type": subject_type,
                "is_default": True,
                "is_active": True,
            },
        )
        if not created and (
            plan.plan_type != SubscriptionPlanType.BASE
            or plan.subject_type != subject_type
            or not plan.is_default
            or not plan.is_active
        ):
            raise ValidationError(f"Le BASE technique {plan.code} existe avec une configuration incompatible.")

        if plan.current_version_id is None:
            version = PlanVersion.objects.create(
                plan=plan,
                version=1,
                name=definition["name"],
                short_description="Socle produit universel Makolo.",
                description="BASE technique minimal requis pour toute Subscription utilisable.",
                catalog_visibility=CatalogVisibility.PUBLIC,
                acquisition_mode=AcquisitionMode.SELF_SERVICE,
                display_order=0,
                change_summary="Version initiale du socle S2.",
            )
            for feature_code, value in definition["entitlements"].items():
                PlanEntitlement.objects.create(
                    plan_version=version,
                    feature=features[feature_code],
                    value=value,
                )
            publish_plan_version(version)
            plan.refresh_from_db()
        plans[subject_type] = plan
    return plans
