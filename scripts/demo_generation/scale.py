#!/usr/bin/env python3
"""Jeu de donnees Makolo : volume + operations reelles en mode DEMO SQLite.

Apercu (defaut): python -m scripts.demo_generation scale.py --journeys 10000 --accesses 10000 --scans 500
Application:    python -m scripts.demo_generation scale.py --journeys 10000 --accesses 10000 --scans 500 --apply
Sans copie et sans backup. N'utiliser que sur une base de demonstration distincte.
Les services canoniques executent les actions (pas de falsification de ScanLog/Payment).
"""
import argparse
import os
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--journeys", type=int, default=0, help="Nombre de paires Occurrence/Profile a preparer")
    parser.add_argument("--accesses", type=int, default=0, help="Nombre de Journey a doter d'Access/QR")
    parser.add_argument("--scans", type=int, default=0, help="Nombre maximal de controles scanner acceptes a simuler")
    parser.add_argument("--orders", type=int, default=0, help="Nombre de commandes Event de demo a tenter")
    parser.add_argument("--queues", type=int, default=0, help="Nombre d'Occurrences avec files Live a alimenter")
    parser.add_argument("--profiles", type=int, default=100, help="Nombre de profils world_ candidats")
    parser.add_argument("--queue-advance", choices=["called", "served"], help="Simuler des transitions de file via les services")
    parser.add_argument("--days", type=int, default=60, help="Horizon des Occurrences futures")
    parser.add_argument("--actor", default="beta_event_manager", help="Operateur Operations non-admin")
    parser.add_argument("--scanner", default="beta_scanner", help="Operateur Scanner non-admin")
    parser.add_argument("--grantor", default="beta_staff", help="Autorite existante qui accorde les roles demo")
    parser.add_argument("--grant-demo-roles", action="store_true", help="Accorder des Mandates limites aux seules Activity demo")
    parser.add_argument("--inventory", action="store_true", help="Inventaire du remplissage de tous les modeles Django")
    parser.add_argument("--max-db-mb", type=int, default=450, help="Seuil d'arret par taille SQLite en Mio")
    parser.add_argument("--apply", action="store_true", help="Appliquer dans SQLite existante; sans copie ni backup")
    args = parser.parse_args(argv)
    if any(not 0 <= getattr(args, name) <= 100000 for name in ("journeys", "accesses", "scans", "orders", "queues")):
        parser.error("Volumes autorises : 0..100000")
    if not 1 <= args.profiles <= 5000 or not 1 <= args.days <= 365 or not 50 <= args.max_db_mb <= 10000:
        parser.error("Bornes de profils, jours ou taille SQLite invalides")

    import django
    django.setup()
    from django.apps import apps
    from django.contrib.auth import get_user_model
    from django.core.exceptions import PermissionDenied, ValidationError
    from django.db import connection, transaction
    from django.db.models import Q
    from django.utils import timezone
    from datetime import timedelta
    from activities.models import ActivityStatus, Occurrence, OccurrenceStatus
    from access.models import Access, AccessStatus, CredentialStatus
    from access.services import issue_access, render_access_credential
    from authorization.constants import SystemRoleCode
    from authorization.services import grant_activity_role, has_platform_authority
    from events.models import Event
    from journeys.models import Journey, WorkflowKind
    from journeys.services import create_journey, submit_journey, confirm_journey
    from operations.checkpoint_models import OccurrenceCheckpoint, CheckpointStatus
    from operations.checkpoint_services import open_checkpoint
    from operations.queue_models import OccurrenceQueue, QueueEntry, QueueEligibilityPolicy, QueueStatus
    from operations.queue_services import enter_queue, call_next, serve_entry
    from operations.permissions import user_can_manage_activity_operations
    from scanner.permissions import user_can_scan_event, user_can_manage_activity_scanner_assignments
    from scanner.models import ScannerAssignment
    from scanner.services import scan_ticket

    if connection.vendor != "sqlite":
        parser.error("Interdit hors SQLite de demonstration")
    db_path = Path(connection.settings_dict["NAME"]).resolve()
    if not db_path.is_file():
        parser.error("Base SQLite Django introuvable : " + str(db_path))
    def check_space():
        size = db_path.stat().st_size / (1024 * 1024)
        if size >= args.max_db_mb:
            raise SystemExit("Seuil SQLite atteint (%.1f MiB): arret sans supprimer de donnees" % size)
    check_space()
    if not any([args.journeys, args.accesses, args.scans, args.orders, args.queues, args.inventory]):
        parser.error("Choisir au moins un module (--journeys/--accesses/--scans/--orders/--queues/--inventory)")

    User = get_user_model()
    profiles = list(User.objects.filter(username__startswith="world_", is_active=True,
        is_staff=False, is_superuser=False).order_by("username")[:args.profiles])
    actor = User.objects.filter(username=args.actor, is_active=True,
        is_staff=False, is_superuser=False).first()
    scanner = User.objects.filter(username=args.scanner, is_active=True,
        is_staff=False, is_superuser=False).first()
    grantor = User.objects.filter(username=args.grantor, is_active=True).first()
    if not profiles and (args.journeys or args.orders):
        parser.error("Aucun beneficiaire world_ actif (demonstration requise)")
    if (args.queues or args.orders) and actor is None:
        parser.error("Operateur Event/Operations non-admin introuvable")
    if args.scans and scanner is None:
        parser.error("Operateur Scanner non-admin introuvable")
    if args.grant_demo_roles and grantor is None:
        parser.error("Grantor introuvable")
    if args.grant_demo_roles and not has_platform_authority(grantor):
        parser.error("Le grantor doit deja disposer d une autorite plateforme explicite")
    if args.orders:
        from django.conf import settings
        from tickets.models import TicketType, TicketOrder
        from tickets.services import create_order, configure_ticket_type
        from payments.models import PaymentProvider, PaymentMethod, PaymentStatus, Payment
        from payments.services import initiate_payment, complete_sandbox_payment
        from events.permissions import user_can_manage_event
        sandbox = bool(getattr(settings, "PAYMENTS_SANDBOX_ENABLED", False))
    now = timezone.now()
    future = now + timedelta(days=args.days)
    occurrences = list(Occurrence.objects.select_related("activity").filter(
        activity__slug__startswith="demo-", activity__status=ActivityStatus.PUBLISHED,
        start_at__isnull=False, end_at__gt=now, start_at__lte=future,
        status=OccurrenceStatus.SCHEDULED,
    ).order_by("start_at", "id")[:10000])
    print("MODE", "APPLICATION" if args.apply else "APERCU", "| SQLite", db_path.name,
          "| Occurrences demo:", len(occurrences), "| profils:", len(profiles))
    counts = Counter()

    # 1. Journey : reutiliser le service et ses validations d'eligibilite.
    # Spread first among distinct Occurrences, especially those live now.
    # The old nested loop spent the entire budget on one Occurrence and left
    # Jour J/Live with no eligible beneficiaries on other Activities.
    considered = 0
    if args.journeys and not profiles:
        parser.error("Aucun profil world_ pour preparer les Journeys")
    for batch in range((args.journeys + max(len(occurrences),1) - 1) // max(len(occurrences),1)):
        if considered >= args.journeys:
            break
        for offset, occurrence in enumerate(occurrences):
            if considered >= args.journeys:
                break
            profile = profiles[(batch + offset) % len(profiles)]
            considered += 1
            exists = Journey.objects.filter(occurrence=occurrence, beneficiary=profile,
                workflow=WorkflowKind.REGISTRATION).exclude(
                status__in=["rejected", "cancelled", "expired"]).exists()
            if exists:
                counts["journey_existing"] += 1
                continue
            if not args.apply:
                counts["journey_planned"] += 1
                continue
            try:
                with transaction.atomic():
                    journey = create_journey(initiated_by=profile, beneficiary=profile,
                        activity=occurrence.activity, occurrence=occurrence,
                        workflow=WorkflowKind.REGISTRATION)
                    submit_journey(journey=journey, actor=profile, reason="demo_volume")
                    confirm_journey(journey=journey, actor=profile, reason="demo_volume")
                counts["journey_created"] += 1
            except (ValidationError, PermissionDenied):
                counts["journey_ineligible"] += 1
            if counts["journey_created"] and counts["journey_created"] % 200 == 0:
                check_space()

    # 2. Access + credentials : 1 droit demo par Journey.
    if args.accesses:
        qs = Journey.objects.filter(
            activity__slug__startswith="demo-", occurrence__end_at__gt=now,
            beneficiary__isnull=False,
        ).exclude(status__in=["rejected", "cancelled", "expired"]).select_related(
            "activity", "occurrence", "beneficiary").order_by("occurrence__start_at", "id")
        for journey in qs[:args.accesses]:
            existing = Access.objects.filter(journey=journey, source_key="makolo-demo-volume").exists()
            if existing:
                counts["access_existing"] += 1
                continue
            if not args.apply:
                counts["access_planned"] += 1
                continue
            try:
                issue_access(beneficiary=journey.beneficiary, activity=journey.activity,
                    occurrence=journey.occurrence, journey=journey,
                    issued_by=grantor, source_key="makolo-demo-volume",
                    create_credential=True, audit_reason="synthetic-demo-volume")
                counts["access_created"] += 1
            except (ValidationError, PermissionDenied):
                counts["access_ineligible"] += 1
            if counts["access_created"] and counts["access_created"] % 200 == 0:
                check_space()

    # 3. Operations : roles par Activity, checkpoint + queue, entrées via service.
    if args.queues:
        for occurrence in occurrences:
            if counts["queues_considered"] >= args.queues:
                break
            if not occurrence.start_at <= now < occurrence.end_at:
                continue
            counts["queues_considered"] += 1
            if args.grant_demo_roles and grantor and user_can_manage_activity_operations(grantor, occurrence.activity):
                if args.apply:
                    grant_activity_role(profile=actor, activity=occurrence.activity,
                        role_code=SystemRoleCode.ACTIVITY_OPERATIONS_MANAGER,
                        granted_by=grantor, source="makolo-demo-volume")
                    counts["ops_mandates_checked"] += 1
            if not user_can_manage_activity_operations(actor, occurrence.activity) and not (
                args.grant_demo_roles and not args.apply
            ):
                counts["ops_no_authority"] += 1
                continue
            journeys = list(Journey.objects.filter(
                activity=occurrence.activity, occurrence=occurrence,
                beneficiary__isnull=False).exclude(
                status__in=["rejected","cancelled","expired"]).select_related(
                "beneficiary").order_by("id")[:12])
            if not journeys:
                counts["ops_no_journey"] += 1
                continue
            if not args.apply:
                counts["ops_planned"] += 1
                continue
            with transaction.atomic():
                checkpoint, created = OccurrenceCheckpoint.objects.get_or_create(
                    occurrence=occurrence, key="demo-volume-accueil",
                    defaults={"label":"Accueil de demonstration", "status":CheckpointStatus.PLANNED})
                counts["checkpoints_created"] += int(created)
                if checkpoint.status == CheckpointStatus.PLANNED:
                    checkpoint = open_checkpoint(actor=actor, checkpoint=checkpoint)
                if checkpoint.status != CheckpointStatus.OPEN or not checkpoint.active:
                    counts["ops_checkpoint_unavailable"] += 1
                    continue
                queue, created = OccurrenceQueue.objects.get_or_create(
                    occurrence=occurrence, key="demo-volume-accueil",
                    defaults={"label":"File d'accueil de demonstration", "checkpoint":checkpoint,
                              "eligibility_policy":QueueEligibilityPolicy.JOURNEY_REQUIRED,
                              "status":QueueStatus.OPEN})
                counts["queues_created"] += int(created)
                if queue.status != QueueStatus.OPEN or queue.checkpoint_id != checkpoint.pk:
                    counts["ops_queue_unavailable"] += 1
                    continue
                seen = set()
                for journey in journeys:
                    if journey.beneficiary_id in seen:
                        continue
                    seen.add(journey.beneficiary_id)
                    before = QueueEntry.objects.filter(queue=queue, profile=journey.beneficiary,
                        status__in=["waiting","called"]).exists()
                    enter_queue(actor=actor, queue=queue, profile=journey.beneficiary,
                        source="makolo-demo-volume", client_reference=str(journey.beneficiary_id)[:64])
                    counts["queue_entries_created"] += int(not before)
                if args.queue_advance and QueueEntry.objects.filter(queue=queue, status="waiting").exists():
                    try:
                        called = call_next(actor=actor, queue=queue)
                        if called is not None:
                            counts["queue_entries_called"] += 1
                            if args.queue_advance == "served":
                                serve_entry(actor=actor, entry=called)
                                counts["queue_entries_served"] += 1
                    except (ValidationError, PermissionDenied):
                        counts["queue_transitions_rejected"] += 1

    # 4. Scanner : creation d'autorite scoped + Assignment (responsabilite),
    # puis appels reels a scan_ticket (AccessUse + ScanLog) dont doublons/refus.
    if args.scans:
        accepted = 0
        # Only inspect events with a currently active Occurrence. Ordering
        # all 8k Event UUIDs previously missed all Live candidates in the cap.
        live_activity_ids = Occurrence.objects.filter(
            start_at__lte=now, end_at__gt=now, status=OccurrenceStatus.SCHEDULED,
            activity__slug__startswith="demo-",
            activity__status=ActivityStatus.PUBLISHED,
        ).values("activity_id")
        events = Event.objects.filter(
            activity_id__in=live_activity_ids,
        ).select_related("activity").order_by("activity__title", "id")
        for event in events[:max(50, min(500, args.scans * 3))]:
            if accepted >= args.scans:
                break
            occurrence = event.primary_occurrence
            if occurrence is None or not (occurrence.start_at and occurrence.end_at
                and occurrence.start_at <= now < occurrence.end_at):
                continue
            if args.grant_demo_roles and grantor and user_can_manage_activity_scanner_assignments(grantor, event.activity):
                if args.apply:
                    grant_activity_role(profile=scanner, activity=event.activity,
                        role_code=SystemRoleCode.ACTIVITY_SCANNER, granted_by=grantor,
                        source="makolo-demo-volume")
                    counts["scanner_mandates_checked"] += 1
            if not user_can_scan_event(scanner, event) and not (args.grant_demo_roles and not args.apply):
                counts["scanner_no_authority"] += 1
                continue
            valid_accesses = Access.objects.filter(
                activity=event.activity, occurrence=occurrence, status=AccessStatus.VALID,
                beneficiary__username__startswith="world_",
                credentials__status=CredentialStatus.ACTIVE,
            ).select_related("beneficiary").distinct().order_by("id")
            if not args.apply:
                counts["scanner_candidates"] += min(valid_accesses.count(), args.scans - accepted)
                continue
            checkpoint = OccurrenceCheckpoint.objects.filter(occurrence=occurrence,
                active=True,status=CheckpointStatus.OPEN,key="demo-volume-accueil").first()
            assignment, created = ScannerAssignment.objects.get_or_create(
                activity=event.activity, occurrence=occurrence, agent=scanner,
                defaults={"event":event, "assigned_by":grantor, "checkpoint":checkpoint,
                          "label":"Controle demo", "notes":"Donnees synthetiques demo"})
            if not created and checkpoint and not assignment.checkpoint_id and assignment.notes == "Donnees synthetiques demo":
                assignment.checkpoint = checkpoint
                assignment.save(update_fields=["checkpoint", "updated_at"])
            counts["scanner_assignments_created"] += int(created)
            for access in valid_accesses:
                if accepted >= args.scans:
                    break
                cred = access.credentials.filter(status=CredentialStatus.ACTIVE).order_by("-version").first()
                if cred is None:
                    continue
                token = render_access_credential(cred)
                client_ref = "dvol-ok-" + access.pk.hex
                try:
                    outcome = scan_ticket(token=token, actor=scanner, event=event,
                        client_reference=client_ref, metadata={"synthetic_demo":True})
                    counts["scan_" + outcome.result] += 1
                    if outcome.accepted:
                        accepted += 1
                        # Distinct reference -> genuine duplicate scan (not an idempotent retry).
                        duplicate = scan_ticket(token=token, actor=scanner, event=event,
                            client_reference="dvol-dup-"+access.pk.hex,
                            metadata={"synthetic_demo":True, "case":"duplicate"})
                        counts["scan_" + duplicate.result] += 1
                except (ValidationError, PermissionDenied):
                    counts["scan_rejected_by_service"] += 1
            if counts["scan_invalid_token"] < 20:
                invalid = scan_ticket(token="synthetic-invalid-demo", actor=scanner,
                    event=event, client_reference="dvol-bad-"+event.pk.hex,
                    metadata={"synthetic_demo":True, "case":"invalid"})
                counts["scan_" + invalid.result] += 1

    # 5. Billetterie / Commerce / Payment sandbox : API existantes seulement.
    if args.orders:
        event_qs = Event.objects.filter(activity__slug__startswith="demo-",
            activity__status=ActivityStatus.PUBLISHED).select_related("activity").order_by("id")
        for event in event_qs[:max(20, min(200, args.orders * 2))]:
            if counts["orders_considered"] >= args.orders:
                break
            if not event.is_registration_open:
                continue
            occurrence = event.primary_occurrence
            if occurrence is None or not occurrence.end_at or occurrence.end_at <= now:
                continue
            tt = TicketType.objects.filter(event=event, offer__occurrence=occurrence,
                is_public=True).select_related("offer").order_by("id").first()
            if tt is None and args.grant_demo_roles and args.apply:
                grant_activity_role(profile=actor, activity=event.activity,
                    role_code=SystemRoleCode.ACTIVITY_LOCAL_MANAGER,
                    granted_by=grantor, source="makolo-demo-volume")
                counts["event_manager_mandates_checked"] += 1
            if tt is None and user_can_manage_event(actor, event):
                if args.apply:
                    try:
                        tt = configure_ticket_type(actor=actor, event=event,
                            occurrence=occurrence, name="Billet standard demo",
                            price=("0.00" if event.pk.int % 4 == 0 else "12.50"),
                            currency="USD", quantity_total=500,
                            min_per_order=1, max_per_order=4)
                        counts["ticket_types_created"] += 1
                    except (ValidationError, PermissionDenied):
                        counts["ticket_type_ineligible"] += 1
            if tt is None:
                counts["orders_no_ticket_type"] += 1
                continue
            for buyer in profiles:
                if counts["orders_considered"] >= args.orders:
                    break
                counts["orders_considered"] += 1
                existing = TicketOrder.objects.filter(event=event,buyer=buyer,
                    items__ticket_type=tt).order_by("created_at","id").first()
                if existing:
                    counts["orders_existing"] += 1
                if not args.apply:
                    counts["orders_planned"] += int(existing is None)
                    continue
                try:
                    order = existing
                    if order is None:
                        order = create_order(buyer=buyer, event=event,
                            customer_name=buyer.get_full_name() or buyer.username,
                            customer_email=buyer.email or (buyer.username+"@example.test"),
                            selections=[(tt,1)], auto_confirm_free=True)
                        counts["orders_created"] += 1
                    if order.total_amount > 0 and sandbox:
                        key = "makolo-demo-order:" + str(order.pk)
                        payment = Payment.objects.filter(idempotency_key=key).first()
                        if payment is None:
                            payment = initiate_payment(order=order, actor=buyer,
                                provider=PaymentProvider.SANDBOX,
                                method=PaymentMethod.MOBILE_MONEY,
                                idempotency_key=key)
                        if payment.status != PaymentStatus.SUCCEEDED:
                            complete_sandbox_payment(payment=payment, actor=buyer)
                            counts["sandbox_payments_completed"] += 1
                    elif order.total_amount > 0:
                        counts["paid_orders_pending_sandbox_disabled"] += 1
                except (ValidationError, PermissionDenied):
                    counts["orders_ineligible"] += 1

    print("RESULTATS:", dict(sorted(counts.items())))
    if args.inventory:
        inventory = []
        for model in apps.get_models():
            try:
                n = model.objects.count()
                inventory.append((model._meta.label, n))
            except Exception:
                inventory.append((model._meta.label, "indisponible"))
        print("MODELES:", len(inventory), "NON_VIDES:",
              sum(isinstance(n,int) and n>0 for _,n in inventory))
        for label, number in sorted(inventory):
            print("MODEL", label, number)
    print("Aucun modele hors flux canonique n'a ete rempli artificiellement.")
    print("Les actions reelles externes ne sont pas simulees; paiements uniquement sandbox.")
    if not args.apply:
        print("APERCU uniquement. Ajouter --apply pour ecrire en place sans copie ni backup.")


if __name__ == "__main__":
    main()
