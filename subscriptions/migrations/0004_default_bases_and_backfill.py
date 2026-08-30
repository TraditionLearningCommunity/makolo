from decimal import Decimal

from django.db import migrations
from django.utils import timezone


FEATURES = {
    "activities.create": {
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
    "team.members": {
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
    "custom_roles": {
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
}

BASES = {
    "profile": {
        "code": "profile.base",
        "name": "Makolo Base — Profil",
        "entitlements": {"activities.create": True},
    },
    "space": {
        "code": "space.base",
        "name": "Makolo Base — Espace",
        "entitlements": {"activities.create": True, "custom_roles": False},
    },
}


def _ensure_features(apps):
    FeatureDefinition = apps.get_model("subscriptions", "FeatureDefinition")
    result = {}
    for code, defaults in FEATURES.items():
        feature, _ = FeatureDefinition.objects.get_or_create(code=code, defaults=defaults)
        result[code] = feature
    return result


def _published_default(apps, subject_type, features):
    SubscriptionPlan = apps.get_model("subscriptions", "SubscriptionPlan")
    PlanVersion = apps.get_model("subscriptions", "PlanVersion")
    PlanEntitlement = apps.get_model("subscriptions", "PlanEntitlement")

    existing = (
        SubscriptionPlan.objects.filter(
            subject_type=subject_type,
            plan_type="base",
            is_default=True,
            is_active=True,
            current_version__status="published",
        )
        .select_related("current_version")
        .first()
    )
    if existing:
        return existing

    definition = BASES[subject_type]
    conflicting_default = SubscriptionPlan.objects.filter(
        subject_type=subject_type,
        plan_type="base",
        is_default=True,
        is_active=True,
    ).first()
    if conflicting_default:
        raise RuntimeError(
            f"BASE {subject_type} par défaut existant sans version publiée; correction catalogue requise avant S2."
        )

    plan, created = SubscriptionPlan.objects.get_or_create(
        code=definition["code"],
        defaults={
            "plan_type": "base",
            "subject_type": subject_type,
            "is_default": True,
            "is_active": True,
        },
    )
    if not created and (
        plan.plan_type != "base"
        or plan.subject_type != subject_type
        or not plan.is_default
        or not plan.is_active
    ):
        raise RuntimeError(f"Le Plan technique {definition['code']} existe avec une configuration incompatible.")

    if plan.current_version_id:
        version = PlanVersion.objects.get(pk=plan.current_version_id)
        if version.status != "published":
            raise RuntimeError(f"Le Plan technique {plan.code} a une current_version non publiée.")
        return plan

    now = timezone.now()
    version = PlanVersion.objects.create(
        plan=plan,
        version=1,
        status="published",
        name=definition["name"],
        short_description="Socle produit universel Makolo.",
        description="BASE technique minimal requis pour toute Subscription utilisable.",
        catalog_visibility="public",
        acquisition_mode="self_service",
        display_order=0,
        change_summary="Version initiale du socle S2.",
        published_at=now,
    )
    for code, value in definition["entitlements"].items():
        PlanEntitlement.objects.create(plan_version=version, feature=features[code], value=value)
    plan.current_version = version
    plan.save(update_fields=["current_version", "updated_at"])
    return plan


def _ensure_subject_subscription(Subscription, SubscriptionItem, *, profile_id=None, space_id=None, plan):
    lookup = {"profile_id": profile_id} if profile_id is not None else {"space_id": space_id}
    subscription, _ = Subscription.objects.get_or_create(**lookup, defaults={"status": "active"})
    if not SubscriptionItem.objects.filter(subscription=subscription, status="active", item_type="base").exists():
        SubscriptionItem.objects.create(
            subscription=subscription,
            plan=plan,
            plan_version_id=plan.current_version_id,
            item_type="base",
            status="active",
            starts_at=timezone.now(),
        )


def seed_bases_and_backfill(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    Organization = apps.get_model("organizations", "Organization")
    Subscription = apps.get_model("subscriptions", "Subscription")
    SubscriptionItem = apps.get_model("subscriptions", "SubscriptionItem")

    features = _ensure_features(apps)
    profile_plan = _published_default(apps, "profile", features)
    space_plan = _published_default(apps, "space", features)

    for profile_id in User.objects.values_list("pk", flat=True).iterator():
        _ensure_subject_subscription(
            Subscription,
            SubscriptionItem,
            profile_id=profile_id,
            plan=profile_plan,
        )
    for space_id in Organization.objects.values_list("pk", flat=True).iterator():
        _ensure_subject_subscription(
            Subscription,
            SubscriptionItem,
            space_id=space_id,
            plan=space_plan,
        )


class Migration(migrations.Migration):
    dependencies = [("subscriptions", "0003_subscription_runtime")]
    operations = [migrations.RunPython(seed_bases_and_backfill, migrations.RunPython.noop)]
