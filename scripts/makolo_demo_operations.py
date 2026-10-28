#!/usr/bin/env python3
"""Scenarios Jour J / Live pour une base locale de demonstration Makolo.

Executer depuis la racine du depot:
  python scripts/makolo_demo_operations.py --actor-id UUID
  python scripts/makolo_demo_operations.py --actor-id UUID --apply

Les creations passent par les modeles canoniques et les services Operations.
Aucun role, mandat, Access ou Journey n'est invente. Pas de copie SQLite.
Les beneficiaires sont choisis uniquement parmi les Journeys deja admissibles.
"""
import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")


def run(args):
    import django
    django.setup()
    from django.contrib.auth import get_user_model
    from django.core.exceptions import PermissionDenied, ValidationError
    from django.db import connection, transaction
    from django.utils import timezone
    from activities.models import ActivityStatus, Occurrence, OccurrenceStatus
    from journeys.models import Journey
    from operations.models import (
        CheckpointStatus, OccurrenceCheckpoint, OccurrenceQueue,
        QueueEligibilityPolicy, QueueStatus, QueueEntry,
    )
    from operations.permissions import user_can_manage_activity_operations
    from operations.queue_services import enter_queue, call_next, serve_entry
    from operations.operation_guards import require_occurrence_live_actionable

    if connection.vendor != "sqlite":
        raise SystemExit("Ce script de demo exige SQLite. Aucun acces PostgreSQL autorise.")
    user = get_user_model().objects.filter(pk=args.actor_id, is_active=True).first()
    if user is None:
        raise SystemExit("Profil operateur inconnu ou inactif. Fournir --actor-id.")
    now = timezone.now()
    # Les occurrences terminees, annulees et les Activity non publiees sont exclues.
    candidates = (
        Occurrence.objects.select_related("activity", "activity__space")
        .filter(activity__status=ActivityStatus.PUBLISHED, start_at__lte=now,
                end_at__gt=now)
        .exclude(status__in=[OccurrenceStatus.CANCELLED, OccurrenceStatus.COMPLETED])
        .order_by("start_at", "id")[:args.max_occurrences * 10]
    )
    counts = {"eligible_occurrences": 0, "checkpoints": 0, "queues": 0,
              "entries": 0, "called": 0, "served": 0,
              "without_authority": 0, "without_beneficiaries": 0,
              "existing_entries": 0, "skipped": 0}
    plan = []
    for occurrence in candidates:
        if len(plan) >= args.max_occurrences:
            break
        if not user_can_manage_activity_operations(user, occurrence.activity):
            counts["without_authority"] += 1
            continue
        try:
            require_occurrence_live_actionable(occurrence, at=now)
        except ValidationError:
            counts["skipped"] += 1
            continue
        subjects = list(
            Journey.objects.filter(occurrence=occurrence, activity=occurrence.activity)
            .exclude(status__in=["rejected", "cancelled", "expired"])
            .filter(beneficiary__isnull=False)
            .select_related("beneficiary")
            .order_by("id")[:args.max_entries]
        )
        distinct = {}
        for journey in subjects:
            distinct.setdefault(journey.beneficiary_id, journey.beneficiary)
        if not distinct:
            counts["without_beneficiaries"] += 1
            continue
        plan.append((occurrence, list(distinct.values())))
    counts["eligible_occurrences"] = len(plan)
    if not args.apply:
        print("APERCU SANS MODIFICATION")
        print("Occurrences operables:", len(plan), "beneficiaires:", sum(len(x[1]) for x in plan))
        print("Absence d'autorite:", counts["without_authority"], "sans Journey:", counts["without_beneficiaries"])
        print("Relancer avec --apply pour creer les scenarios, sans copie ni sauvegarde.")
        return

    with transaction.atomic():
        for occurrence, profiles in plan:
            # Cle stable: reexecution ne multiplie pas les scenarios.
            checkpoint, created = OccurrenceCheckpoint.objects.get_or_create(
                occurrence=occurrence, key="demo-live-accueil",
                defaults={"label": "Accueil demo Live", "position": 10,
                          "status": CheckpointStatus.OPEN, "active": True},
            )
            counts["checkpoints"] += int(created)
            if not checkpoint.active or checkpoint.status != CheckpointStatus.OPEN:
                counts["skipped"] += 1
                continue
            queue, created = OccurrenceQueue.objects.get_or_create(
                occurrence=occurrence, key="demo-live-accueil",
                defaults={"checkpoint": checkpoint, "label": "File d'accueil demo",
                          "eligibility_policy": QueueEligibilityPolicy.JOURNEY_REQUIRED,
                          "status": QueueStatus.OPEN},
            )
            counts["queues"] += int(created)
            if queue.status != QueueStatus.OPEN or queue.eligibility_policy != QueueEligibilityPolicy.JOURNEY_REQUIRED:
                counts["skipped"] += 1
                continue
            if queue.checkpoint_id != checkpoint.pk:
                counts["skipped"] += 1
                continue
            before = QueueEntry.objects.filter(queue=queue).count()
            for profile in profiles:
                # Controle d'autorite, eligibilite canonique, FIFO, idempotence et
                # Domain Events sont assures par le service, non par du SQL direct.
                try:
                    enter_queue(actor=user, queue=queue, profile=profile,
                                source="makolo-demo", client_reference=str(profile.pk)[:64])
                except (ValidationError, PermissionDenied):
                    counts["skipped"] += 1
            after = QueueEntry.objects.filter(queue=queue).count()
            counts["entries"] += after - before
            counts["existing_entries"] += max(0, len(profiles) - (after - before))
            if args.advance and after:
                # Le service applique les transitions canoniques FIFO.
                try:
                    called = call_next(actor=user, queue=queue)
                    if called:
                        counts["called"] += 1
                        if args.advance == "served":
                            serve_entry(actor=user, entry=called)
                            counts["served"] += 1
                except (ValidationError, PermissionDenied):
                    counts["skipped"] += 1
    print("Scenarios operationnels verifies et appliques:", counts)
    print("Les permissions et droits n'ont pas ete modifies.")
    print("Aucun AccessCredential, AccessUse, ScanLog ou preuve de passage n'a ete fabrique.")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--actor-id", required=True, help="UUID d'un operateur demo autorise")
    p.add_argument("--max-occurrences", type=int, default=20)
    p.add_argument("--max-entries", type=int, default=12)
    p.add_argument("--advance", choices=["called", "served"], help="Faire avancer une entree via services")
    p.add_argument("--apply", action="store_true", help="Mutation en place, sans copie ni backup")
    a = p.parse_args()
    if not (1 <= a.max_occurrences <= 200 and 1 <= a.max_entries <= 100):
        p.error("Limites: 1..200 occurrences et 1..100 entrees")
    run(a)


if __name__ == "__main__":
    main()
