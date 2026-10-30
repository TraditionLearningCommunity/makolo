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



def prepare_demo_roles(grantor, apply, limit, transport_ids=(), event_ids=()):
    from django.contrib.auth import get_user_model
    from activities.models import Activity
    from django.db.models import Q
    import unicodedata
    def normalize(value):
        return ''.join(c for c in unicodedata.normalize('NFKD', (value or '').lower()) if not unicodedata.combining(c))
    from authorization.constants import SystemRoleCode
    from authorization.services import grant_activity_role
    from operations.permissions import user_can_manage_activity_operations
    users = get_user_model()
    for name, terms in (
        ("beta_transport_operator", ("transport", "bus", "voyage", "navette", "trajet")),
        ("beta_event_manager", ("concert", "event", "evenement", "festival", "conference", "spectacle", "atelier")),
    ):
        profile = users.objects.filter(username=name, is_active=True, is_staff=False, is_superuser=False).first()
        if profile is None:
            print(name, "absent ou non conforme")
            continue
        matches = []
        explicit_ids = transport_ids if name == "beta_transport_operator" else event_ids
        candidates = Activity.objects.filter(pk__in=explicit_ids).order_by("id") if explicit_ids else Activity.objects.filter(Q(slug__startswith="demo-2026-q4-") | Q(slug__startswith="demo-")).order_by("id")
        for activity in candidates:
            label = normalize((activity.slug or "") + " " + (activity.title or ""))
            if (explicit_ids or any(term in label for term in terms)) and user_can_manage_activity_operations(grantor, activity):
                matches.append(activity)
                if len(matches) >= limit:
                    break
        print(name, "activites demo eligibles:", len(matches))
        if not matches:
            print("  Aucune activite correspondante. Fournir des UUID explicites apres verification des Activity demo.")
        for activity in matches:
            print("  ", activity.pk, activity.title)
        if apply:
            for activity in matches:
                grant_activity_role(profile=profile, activity=activity,
                    role_code=SystemRoleCode.ACTIVITY_OPERATIONS_MANAGER,
                    granted_by=grantor, source="makolo-demo-operations")
            print(name, "mandats verifies/attribues:", len(matches))

def run(args):
    import django
    django.setup()
    from django.contrib.auth import get_user_model
    from django.core.exceptions import PermissionDenied, ValidationError
    from django.db import connection, transaction
    from django.utils import timezone
    from activities.models import ActivityStatus, Occurrence, OccurrenceStatus
    from journeys.models import Journey
    from access.models import Access, AccessCredential, AccessStatus, CredentialStatus
    from access.services import issue_access, validate_access
    from payments.models import Payment, PaymentProvider, PaymentMethod, PaymentStatus
    from payments.services import initiate_payment, complete_sandbox_payment
    from tickets.models import TicketOrder, TicketOrderStatus, Ticket
    from scanner.services import scan_ticket
    from scanner.permissions import user_can_scan_event
    from operations.checkpoint_models import CheckpointStatus, OccurrenceCheckpoint
    from operations.queue_models import OccurrenceQueue, QueueEligibilityPolicy, QueueStatus, QueueEntry
    from operations.permissions import user_can_manage_activity_operations
    from operations.queue_services import enter_queue, call_next, serve_entry
    from operations.operation_guards import require_occurrence_live_actionable

    if connection.vendor != "sqlite":
        raise SystemExit("Ce script de demo exige SQLite. Aucun acces PostgreSQL autorise.")
    if args.prepare_demo_roles:
        grantor = get_user_model().objects.filter(pk=args.grantor_id, is_active=True).first()
        if not grantor:
            raise SystemExit("Grantor introuvable ou inactif")
        with transaction.atomic():
            prepare_demo_roles(grantor, args.apply, args.max_occurrences, args.transport_activity_id, args.event_activity_id)
        return
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
              "existing_entries": 0, "access_issued": 0, "access_uses": 0, "payments": 0, "scans": 0, "skipped": 0}
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
        print("Paiement sandbox et scan de billets existants possibles avec --demo-payments et --demo-ticket-scans.")
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

            if args.demo_access:
                for profile in profiles:
                    journey = Journey.objects.filter(
                        occurrence=occurrence, activity=occurrence.activity,
                        beneficiary=profile,
                    ).exclude(status__in=["rejected", "cancelled", "expired"]).order_by("id").first()
                    if journey is None:
                        continue
                    try:
                        existing = Access.objects.filter(
                            journey=journey, source_key="makolo-demo-live",
                        ).exists()
                        access = issue_access(
                            beneficiary=profile, activity=occurrence.activity,
                            occurrence=occurrence, journey=journey,
                            issued_by=user, source_key="makolo-demo-live",
                            audit_reason="Simulation Makolo",
                        )
                        counts["access_issued"] += int(not existing)
                        if args.demo_scan and access.status == AccessStatus.VALID:
                            credential = AccessCredential.objects.filter(
                                access=access, status=CredentialStatus.ACTIVE
                            ).order_by("-version").first()
                            if credential:
                                outcome = validate_access(
                                    access=access, credential=credential, controller=user,
                                    expected_activity=occurrence.activity,
                                    expected_occurrence=occurrence, source="makolo-demo",
                                    client_reference="demo-"+str(access.pk)[:36],
                                )
                                counts["access_uses"] += int(outcome.use is not None and outcome.accepted)
                    except (ValidationError, PermissionDenied):
                        counts["skipped"] += 1
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

    if args.demo_payments or args.demo_ticket_scans:
        from django.conf import settings
        if args.demo_payments and not getattr(settings, "PAYMENTS_SANDBOX_ENABLED", False):
            raise SystemExit("Paiements sandbox desactives dans Django; ne pas contourner le provider.")
        # Un paiement appartient au buyer et un scan au scanner autorise.
        # On travaille sur les commandes/billets deja emis, sans manipuler
        # directement les statuts ni recreer d'autres verites commerciales.
        if args.apply:
            if args.demo_payments:
                orders = TicketOrder.objects.filter(buyer=user).order_by("pk")[:args.max_entries]
                for order in orders:
                    try:
                        key="makolo-demo-payment:"+str(order.pk)
                        old=Payment.objects.filter(idempotency_key=key).first()
                        if old is None:
                            payment=initiate_payment(
                                order=order,actor=user,provider=PaymentProvider.SANDBOX,
                                method=PaymentMethod.MOBILE_MONEY,
                                idempotency_key=key,
                            )
                        else:
                            payment=old
                        if payment.status not in (PaymentStatus.SUCCEEDED,PaymentStatus.REFUNDED):
                            complete_sandbox_payment(payment=payment,actor=user)
                            counts["payments"]+=1
                    except (ValidationError,PermissionDenied):
                        counts["skipped"]+=1
            if args.demo_ticket_scans:
                tickets=Ticket.objects.filter(order__buyer=user).select_related("order","order__event").order_by("pk")[:args.max_entries]
                for ticket in tickets:
                    event=ticket.order.event
                    if not user_can_scan_event(user,event):
                        counts["skipped"]+=1
                        continue
                    try:
                        outcome=scan_ticket(
                            token=ticket.qr_token,actor=user,event=event,
                            client_reference="demo-ticket-"+str(ticket.pk)[:35],
                            metadata={"synthetic_demo":True},
                        )
                        if outcome.accepted: counts["scans"]+=1
                    except (ValidationError,PermissionDenied):
                        counts["skipped"]+=1
    print("Scenarios operationnels verifies et appliques:", counts)
    print("Les permissions et droits n'ont pas ete modifies.")
    print("Les AccessUse et ScanLog eventuels proviennent des services canoniques.")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--actor-id", help="UUID operateur demo")
    p.add_argument("--prepare-demo-roles", action="store_true")
    p.add_argument("--grantor-id", help="UUID autorite de concession")
    p.add_argument("--transport-activity-id", action="append", default=[], help="UUID explicite Activity transport demo, repetable")
    p.add_argument("--event-activity-id", action="append", default=[], help="UUID explicite Activity evenement demo, repetable")
    p.add_argument("--max-occurrences", type=int, default=20)
    p.add_argument("--max-entries", type=int, default=12)
    p.add_argument("--advance", choices=["called", "served"], help="Faire avancer une entree via services")
    p.add_argument("--demo-access", action="store_true", help="Emettre Access et credentials via le service canonique")
    p.add_argument("--demo-payments", action="store_true", help="Completer les paiements sandbox de commandes appartenant a l acteur")
    p.add_argument("--demo-ticket-scans", action="store_true", help="Scanner les billets existants si l acteur possede autorite scanner")
    p.add_argument("--demo-scan", action="store_true", help="Valider Access et enregistrer AccessUse via le service canonique")
    p.add_argument("--apply", action="store_true", help="Mutation en place, sans copie ni backup")
    a = p.parse_args()
    if not (1 <= a.max_occurrences <= 200 and 1 <= a.max_entries <= 100):
        p.error("Limites: 1..200 occurrences et 1..100 entrees")
    if a.demo_scan and not a.demo_access:
        p.error("--demo-scan exige --demo-access")
    if a.prepare_demo_roles and not a.grantor_id:
        p.error("--grantor-id requis")
    if not a.prepare_demo_roles and not a.actor_id:
        p.error("--actor-id requis")
    run(a)


if __name__ == "__main__":
    main()
