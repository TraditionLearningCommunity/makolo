"""Après l'action : Journey réalisée, Proof privée et Goals recalculés.

Aucune réussite n'est inventée : une Journey ne peut être clôturée ici que
lorsqu'un AccessUse accepté atteste une action passée par les services Makolo.
"""
import argparse
from collections import Counter


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--count", type=int, default=50)
    p.add_argument("--apply", action="store_true")
    a = p.parse_args(argv)
    if not 1 <= a.count <= 10000:
        p.error("count 1..10000")
    import django
    django.setup()
    from django.core.exceptions import PermissionDenied, ValidationError
    from django.contrib.auth import get_user_model
    from django.db import connection, transaction
    from access.models import AccessUseResult
    from journeys.models import Journey, JourneyStatus, WorkflowKind
    from journeys.services import fulfill_journey
    from trust.models import Proof, ProofType
    from trust.services import issue_proof
    from goals.services import evaluate_goals
    if connection.vendor != "sqlite":
        p.error("SQLite de demonstration obligatoire")
    counts = Counter()
    qs = (Journey.objects.filter(
        activity__slug__startswith="demo-",
        beneficiary__username__startswith="world_",
        status=JourneyStatus.CONFIRMED,
        accesses__uses__result=AccessUseResult.ACCEPTED,
    ).exclude(workflow=WorkflowKind.SERVICE).select_related(
        "beneficiary", "activity").distinct().order_by("id")[:a.count])
    completed_profiles = set()
    for journey in qs:
        if not a.apply:
            counts["journeys_to_fulfill"] += 1
            continue
        try:
            with transaction.atomic():
                fulfill_journey(journey=journey, actor=journey.beneficiary,
                    reason="demo_access_use_accepted")
                counts["journeys_fulfilled"] += 1
                if not Proof.objects.filter(
                    journey=journey, proof_type=ProofType.JOURNEY_COMPLETED
                ).exists():
                    issue_proof(journey=journey,
                        proof_type=ProofType.JOURNEY_COMPLETED,
                        actor=None, is_public=False)
                    counts["proofs_issued"] += 1
            completed_profiles.add(journey.beneficiary_id)
        except (ValidationError, PermissionDenied):
            counts["journeys_not_eligible"] += 1
    if a.apply:
        for pk in completed_profiles:
            profile = get_user_model().objects.get(pk=pk)
            try:
                with transaction.atomic():
                    outcomes = evaluate_goals(profile=profile)
                counts["goals_completed"] += len(outcomes)
            except (ValidationError, PermissionDenied):
                counts["goal_evaluations_rejected"] += 1
    print("AFTERCARE", "APPLY" if a.apply else "PREVIEW",
          dict(sorted(counts.items())))


if __name__ == "__main__":
    main()
