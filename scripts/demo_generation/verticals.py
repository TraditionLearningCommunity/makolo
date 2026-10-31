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
    from opportunities.models import Opportunity, OpportunitySave, OpportunitySubmission, OpportunitySource, OpportunitySubmissionStatus
    from opportunities.services import save_opportunity, submit_opportunity, start_submission_review, decide_opportunity_submission
    from obtention.models import ObtentionDetails, ObtentionConfiguration, ObtentionMode, ObtentionJourneyContext
    from obtention.services import create_obtention_journey
    from services.models import ServiceDetails, ServiceJourneyContext
    from services.services import create_service_journey
    from funding.models import FundingDetails, FundingContribution
    from funding.services import create_funding_contribution
    from django.test.utils import override_settings
    from payments.models import Payment, PaymentProvider, PaymentMethod, PaymentStatus
    from payments.services import initiate_obligation_payment, complete_sandbox_payment
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
    for opp, user in pairs(Opportunity.objects.filter(publication_status="published", merged_into__isnull=True).order_by("id")[:a.per_domain] if "opportunities" in selected else []):
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

    # Simulated profiles recommend actual published Opportunity source URLs;
    # the proposal and curator review are canonical, with no external submit.
    if "opportunities" in selected:
        sources = (OpportunitySource.objects.filter(
            opportunity__publication_status="published", status="active"
        ).select_related("opportunity", "opportunity__current_revision")
         .order_by("-is_primary", "id")[:a.per_domain])
        staff = get_user_model().objects.filter(
            username="beta_staff", is_active=True).first()
        for index, source in enumerate(sources):
            user = profiles[index % len(profiles)]
            note = "[DEMO] Source suggeree depuis une veille fictive"
            submission = OpportunitySubmission.objects.filter(
                submitted_by=user, url=source.url, comment=note).order_by("id").first()
            if submission:
                counts["opportunity_submissions_existing"] += 1
            elif not a.apply:
                counts["opportunity_submissions_planned"] += 1
                continue
            else:
                try:
                    with transaction.atomic():
                        submission = submit_opportunity(
                            submitted_by=user, url=source.url,
                            title="[DEMO] Proposition " + str(index + 1),
                            comment=note)
                    counts["opportunity_submissions_created"] += 1
                except (ValidationError, PermissionDenied):
                    counts["opportunity_submissions_ineligible"] += 1
                    continue
            if staff and submission.status == OpportunitySubmissionStatus.PENDING:
                if a.apply:
                    try:
                        with transaction.atomic():
                            start_submission_review(submission=submission, actor=staff)
                            decide_opportunity_submission(
                                submission=submission, actor=staff,
                                decision=OpportunitySubmissionStatus.DUPLICATE,
                                resolved_opportunity=source.opportunity,
                                review_note="Demo : source deja connue, proposition dedupliquee.")
                        counts["opportunity_submissions_reviewed"] += 1
                    except (ValidationError, PermissionDenied):
                        counts["opportunity_submissions_pending_review"] += 1
                else:
                    counts["opportunity_submissions_review_planned"] += 1

    # Contribution financiere : intention seulement. Payment reste la verite d'execution.
    for funding, user in pairs(FundingDetails.objects.select_related("activity").filter(activity__slug__startswith="demo-").order_by("id")[:a.per_domain] if "funding" in selected else []):
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
    for service, user in pairs(ServiceDetails.objects.select_related("activity").filter(activity__slug__startswith="demo-").order_by("id")[:a.per_domain] if "services" in selected else []):
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
    details = ObtentionDetails.objects.select_related("activity").filter(activity__slug__startswith="demo-").order_by("id")[:a.per_domain] if "obtention" in selected else []
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

    # Funding payment is a *real sandbox service transition* from its
    # existing PaymentObligation. Never produce fake settled ledger rows.
    if "funding" in selected:
        sandbox_enabled = connection.vendor == "sqlite"
        contributions = (FundingContribution.objects.filter(
            funding__activity__slug__startswith="demo-generation-funding-",
            contributor_profile__username__startswith="world_",
            payment_obligation__isnull=False,
        ).select_related("payment_obligation", "contributor_profile")
         .order_by("id")[:a.per_domain])
        for contribution in contributions:
            obligation = contribution.payment_obligation
            if Payment.objects.filter(
                obligation=obligation, status=PaymentStatus.SUCCEEDED
            ).exists():
                counts["funding_payments_existing"] += 1
                continue
            if not sandbox_enabled:
                counts["funding_payments_sandbox_disabled"] += 1
                continue
            if not a.apply:
                counts["funding_payments_planned"] += 1
                continue
            try:
                with override_settings(PAYMENTS_SANDBOX_ENABLED=True):
                    with transaction.atomic():
                        payment = initiate_obligation_payment(
                            obligation=obligation, actor=contribution.contributor_profile,
                            provider=PaymentProvider.SANDBOX,
                            method=PaymentMethod.MOBILE_MONEY,
                            idempotency_key="makolo-demo-funding:" + str(contribution.pk))
                        if payment.status != PaymentStatus.SUCCEEDED:
                            complete_sandbox_payment(
                                payment=payment, actor=contribution.contributor_profile)
                counts["funding_payments_completed"] += 1
            except (ValidationError, PermissionDenied):
                counts["funding_payments_rejected"] += 1

    print("MODE:", "APPLY" if a.apply else "APERCU")
    print("RESULTATS:",dict(sorted(counts.items())))
    print("Aucun paiement bancaire, vraie soumission externe, livraison ni preuve invente.")


if __name__ == "__main__":
    main()
