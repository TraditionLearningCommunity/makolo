"""Catalogue d'abonnements de DEMONSTRATION, idempotent et opt-in.

Les montants ne sont PAS des tarifs commerciaux officiels de Makolo. Ne
modifie jamais un forfait existant ou une version deja publiee.
"""
import argparse
from decimal import Decimal


DEMO_OFFERS = (
    ("profile", "base", "demo.profile.plus", "Profil Plus", "7.00", "month", 1),
    ("profile", "base", "demo.profile.max", "Profil Max", "18.00", "month", 1),
    ("profile", "addon", "demo.profile.option", "Option Profil", "3.00", "month", 1),
    ("space", "base", "demo.space.equipe", "Espace Équipe", "15.00", "month", 1),
    ("space", "base", "demo.space.organisation", "Espace Organisation", "39.00", "month", 1),
    ("space", "addon", "demo.space.option", "Option Espace", "5.00", "month", 1),
)


# These are exercise labels, not commercial promises or additional rights.
# The three existing canonical features cannot justify inventing a separate
# Profile entitlement for Plus vs Max. Actual differences remain server-owned.
DEMO_BENEFIT_LABELS = {
    "demo.profile.plus": "Fonctionnalités avancées pour vos démarches",
    "demo.profile.max": "Capacité étendue pour vos activités personnelles",
    "demo.profile.option": "Capacités complémentaires au forfait personnel",
    "demo.space.equipe": "Jusqu’à 5 membres d’équipe actifs",
    "demo.space.organisation": "Jusqu’à 25 membres et rôles personnalisés",
    "demo.space.option": "3 membres d’équipe supplémentaires",
}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--apply", action="store_true")
    a = p.parse_args(argv)
    import django
    django.setup()
    from django.db import connection, transaction
    from subscriptions.models import SubscriptionPlan, PlanVersion, PlanBenefit, PlanEntitlement, FeatureDefinition
    from subscriptions.billing_models import PlanVersionBillingTerms
    from subscriptions.services import publish_plan_version
    from subscriptions.contracts import PlanVersionStatus
    if connection.vendor != "sqlite":
        p.error("Catalogue demo pour SQLite de test uniquement")
    created = existing = 0
    for subject, kind, code, name, amount, unit, frequency in DEMO_OFFERS:
        plan = SubscriptionPlan.objects.filter(code=code).first()
        if plan is not None:
            if plan.subject_type != subject or plan.plan_type != kind:
                p.error("Collision de code catalogue: " + code)
            existing += 1
            continue
        if not a.apply:
            print("CATALOG PLANNED", code, name, amount, "USD/"+unit)
            created += 1
            continue
        with transaction.atomic():
            plan = SubscriptionPlan.objects.create(
                code=code, plan_type=kind, subject_type=subject,
                is_default=False, is_active=True,
            )
            version = PlanVersion.objects.create(
                plan=plan, version=1, name=name,
                short_description="Formule pour accompagner vos activités et démarches.",
                description="Accès aux fonctionnalités prévues par cette formule et ses conditions.",
            )
            entitlements = (
                {"activities.create": True} if subject == "profile" else
                {"activities.create": True, "team.members": 5 if code.endswith("equipe") else 25,
                 "custom_roles": code.endswith("organisation") or code.endswith("option")}
            )
            if kind == "addon":
                entitlements = {"activities.create": True} if subject == "profile" else {"team.members": 3}
            for feature_code, value in entitlements.items():
                feature = FeatureDefinition.objects.get(code=feature_code, is_active=True)
                PlanEntitlement.objects.create(plan_version=version, feature=feature, value=value)
            PlanBenefit.objects.create(
                plan_version=version,
                title=DEMO_BENEFIT_LABELS[code],
                position=0,
            )
            PlanVersionBillingTerms.objects.create(
                plan_version=version, amount=Decimal(amount),
                currency="USD", billing_period_unit=unit,
                billing_period_count=frequency,
                payment_due_days=7, grace_period_days=3,
            )
            publish_plan_version(version)
            created += 1
    print("DEMO CATALOG", "APPLY" if a.apply else "PREVIEW",
          {"new":created,"existing":existing})
    print("Tarifs fictifs; entitlements sur Features existantes, pas de permission implicite.")


if __name__ == "__main__":
    main()
