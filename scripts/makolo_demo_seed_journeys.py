#!/usr/bin/env python3
"""Prepare des Journey de demonstration sur les Occurrences actives, sans copie BDD.

Usage:
  python scripts/makolo_demo_seed_journeys.py
  python scripts/makolo_demo_seed_journeys.py --apply
Le script n'accorde aucune autorite. Les services Django valident les transitions.
"""
import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--apply", action="store_true")
    p.add_argument("--occurrences", type=int, default=30)
    p.add_argument("--beneficiaries", type=int, default=6)
    a = p.parse_args()
    if not 1 <= a.occurrences <= 100 or not 1 <= a.beneficiaries <= 30:
        p.error("bornes: --occurrences 1..100, --beneficiaries 1..30")
    import django
    django.setup()
    from django.contrib.auth import get_user_model
    from django.core.exceptions import ValidationError
    from django.db import connection, transaction
    from django.utils import timezone
    from activities.models import ActivityStatus, Occurrence, OccurrenceStatus
    from journeys.models import Journey, WorkflowKind
    from journeys.services import create_journey, submit_journey, confirm_journey
    if connection.vendor != "sqlite":
        p.error("Reserve aux bases SQLite de demonstration")
    profiles = list(get_user_model().objects.filter(
        username__startswith="world_", is_active=True, is_staff=False,
        is_superuser=False).order_by("username")[:a.beneficiaries])
    if not profiles:
        p.error("aucun profil world_ de demonstration disponible")
    now = timezone.now()
    occurrences = list(
        Occurrence.objects.select_related("activity")
        .filter(activity__slug__startswith="demo-", activity__status=ActivityStatus.PUBLISHED,
                start_at__lte=now, end_at__gt=now)
        .exclude(status__in=[OccurrenceStatus.CANCELLED, OccurrenceStatus.COMPLETED])
        .order_by("start_at", "id")[:a.occurrences]
    )
    print("Occurences candidates:", len(occurrences), "| profils demo:", len(profiles))
    counts = dict(created=0, existing=0, ineligible=0)
    with transaction.atomic():
        for occurrence in occurrences:
            for profile in profiles:
                existing = Journey.objects.filter(
                    activity=occurrence.activity, occurrence=occurrence,
                    beneficiary=profile, workflow=WorkflowKind.REGISTRATION,
                ).exclude(status__in=["rejected", "cancelled", "expired"]).exists()
                if existing:
                    counts["existing"] += 1
                    continue
                if not a.apply:
                    counts["created"] += 1
                    continue
                try:
                    with transaction.atomic():
                        journey = create_journey(
                            initiated_by=profile, beneficiary=profile,
                            activity=occurrence.activity, occurrence=occurrence,
                            workflow=WorkflowKind.REGISTRATION)
                        submit_journey(journey=journey, actor=profile, reason="demo_seed")
                        confirm_journey(journey=journey, actor=profile, reason="demo_seed")
                    counts["created"] += 1
                except ValidationError:
                    counts["ineligible"] += 1
        if not a.apply:
            print("APERCU - aucune modification")
    print("Journeys:", counts)
    if not occurrences:
        print("Aucune Occurrence active avec slug demo-. Recaler les dates de demo ou examiner les donnees.")


if __name__ == "__main__":
    main()
