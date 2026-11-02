"""Catalogue d'abonnements de DEMONSTRATION, idempotent et opt-in.

Les montants ne sont PAS des tarifs commerciaux officiels de Makolo. Ne
modifie jamais un forfait existant ou une version deja publiee.
"""
import argparse
from decimal import Decimal


DEMO_OFFERS = (
    ("profile", "base", "demo.profile.plus", "DEMO Profil Plus", "7.00", "month", 1),
    ("profile", "base", "demo.profile.max", "DEMO Profil Max", "18.00", "month", 1),
    ("profile", "addon", "demo.profile.option", "DEMO Option Profil", "3.00", "month", 1),
    ("space", "base", "demo.space.equipe", "DEMO Espace Equipe", "15.00", "month", 1),
    ("space", "base", "demo.space.organisation", "DEMO Espace Organisation", "39.00", "month", 1),
    ("space", "addon", "demo.space.option", "DEMO Option Espace", "5.00", "month", 1),
)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--apply", action="store_true")
    a = p.parse_args(argv)
    import django
    django.setup()
    from django.db import connection, transaction
    from subscriptions.models import SubscriptionPlan, PlanVersion, PlanBenefit
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
                short_description="Offre fictive pour la validation de Makolo.",
                description="Données de démonstration uniquement. Pas une offre commerciale.",
            )
            PlanBenefit.objects.create(
                plan_version=version,
                title="Scénarios de démonstration et facturation sandbox",
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
    print("Tarifs uniquement fictifs, sans promesse de capacités supplémentaires.")


if __name__ == "__main__":
    main()
