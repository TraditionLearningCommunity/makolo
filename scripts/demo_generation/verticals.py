#!/usr/bin/env python3
"""Diversifier les scenarios demo : Opportunity, Service, Obtention et financement.

Apercu par defaut; --apply pour ecrire en SQLite de demonstration.
Les domaines sont modifies UNIQUEMENT via leurs services; aucun versement reel.
"""
import argparse
import os
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--per-domain", type=int, default=50)
    p.add_argument("--profiles", type=int, default=30)
    p.add_argument("--apply", action="store_true")
    p.add_argument("--domains", default="opportunities,services,obtention,funding")
    a = p.parse_args(argv)
    selected = set(a.domains.split(","))
    if not selected or not selected <= {"opportunities", "services", "obtention", "funding"}:
        p.error("Domaines attendus: opportunities,services,obtention,funding")
    if not 1 <= a.per_domain <= 2000 or not 1 <= a.profiles <= 100:
        p.error("Limites : --per-domain 1..2000, --profiles 1..100")
    import django
    django.setup()
    from django.contrib.auth import get_user_model
    from django.core.exceptions import ValidationError, PermissionDenied
    from django.db import connection, transaction
    from opportunities.models import Opportunity, OpportunitySave, OpportunitySubmission
    from opportunities.services import save_opportunity, submit_opportunity
    from obtention.models import ObtentionDetails, ObtentionConfiguration, ObtentionMode, ObtentionJourneyContext
    from obtention.services import create_obtention_journey
    from services.models import ServiceDetails, ServiceJourneyContext
    from services.services import create_service_journey
    from funding.models import FundingDetails, FundingContribution
    from funding.services import create_funding_contribution
    if connection.vendor != "sqlite":
        p.error("SQLite de demonstration obligatoire")
    profiles = list(get_user_model().objects.filter(username__startswith="world_",
        is_active=True, is_staff=False, is_superuser=False).order_by("username")[:a.profiles])
    if not profiles:
        p.error("Aucun utilisateur world_")
    counts = Counter()
    def pairs(items):
        done = 0
        for item in items:
            for user in profiles:
                if done >= a.per_domain:
                    return
                done += 1
                yield item, user

    # Opportunity : sauvegarde et signalement synthetique, sans inventer une source verifiee.
    for opp, user in pairs(Opportunity.objects.order_by("id")[:a.per_domain] if "opportunities" in selected else []):
        if OpportunitySave.objects.filter(profile=user,opportunity=opp).exists():
            counts["opportunity_saved_existing"] += 1
        elif not a.apply:
            counts["opportunity_saved_planned"] += 1
        else:
            try:
                with transaction.atomic():
                    save_opportunity(profile=user, opportunity=opp)
                counts["opportunity_saved"] += 1
            except (ValidationError, PermissionDenied):
                counts["opportunity_skipped"] += 1

    # Contribution financiere : intention seulement. Payment reste la verite d'execution.
    for funding, user in pairs(FundingDetails.objects.select_related("activity").order_by("id")[:a.per_domain] if "funding" in selected else []):
        ref = "makolo-demo-funding-" + user.pk.hex
        if FundingContribution.objects.filter(funding=funding,contributor_profile=user,client_reference=ref).exists():
            counts["funding_existing"] += 1
        elif not a.apply:
            counts["funding_planned"] += 1
        else:
            try:
                with transaction.atomic():
                    create_funding_contribution(funding=funding,actor=user,amount="5.00",client_reference=ref)
                counts["funding_created"] += 1
            except (ValidationError,PermissionDenied):
                counts["funding_ineligible"] += 1

    # Service : Journey de demande avec ServiceJourneyContext coherent.
    for service, user in pairs(ServiceDetails.objects.select_related("activity").order_by("id")[:a.per_domain] if "services" in selected else []):
        if ServiceJourneyContext.objects.filter(journey__activity=service.activity,
                                                journey__beneficiary=user).exists():
            counts["service_existing"] += 1
        elif not a.apply:
            counts["service_planned"] += 1
        else:
            try:
                with transaction.atomic():
                    create_service_journey(service=service,initiated_by=user,beneficiary=user,
                        objective="Demande fictive de service pour les tests Makolo")
                counts["service_created"] += 1
            except (ValidationError,PermissionDenied):
                counts["service_ineligible"] += 1

    # Obtention : seulement une configuration publiee avec un mode vraiment attache.
    details = ObtentionDetails.objects.select_related("activity").order_by("id")[:a.per_domain] if "obtention" in selected else []
    for obtention, user in pairs(details):
        if ObtentionJourneyContext.objects.filter(journey__activity=obtention.activity,
                                                  journey__beneficiary=user).exists():
            counts["obtention_existing"] += 1
            continue
        conf = ObtentionConfiguration.objects.filter(obtention=obtention,status="published").order_by("-created_at").first()
        mode = ObtentionMode.objects.filter(configuration=conf).order_by("id").first() if conf else None
        if mode is None:
            counts["obtention_no_published_mode"] += 1
            continue
        if not a.apply:
            counts["obtention_planned"] += 1
        else:
            try:
                with transaction.atomic():
                    create_obtention_journey(obtention=obtention,actor=user,mode=mode,beneficiary=user)
                counts["obtention_created"] += 1
            except (ValidationError,PermissionDenied):
                counts["obtention_ineligible"] += 1

    print("MODE:", "APPLY" if a.apply else "APERCU")
    print("RESULTATS:",dict(sorted(counts.items())))
    print("Aucun paiement bancaire, vraie soumission externe, livraison ni preuve invente.")


if __name__ == "__main__":
    main()
