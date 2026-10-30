#!/usr/bin/env python3
"""Demo transport : departs reels de test, Journey, Access, AccessUse, file Live.

Apercu: python -m scripts.demo_generation transport.py
Ecrire : python -m scripts.demo_generation transport.py --apply
SQLite seulement, aucune copie ou sauvegarde automatique, donnees marquees demo-.
"""
import argparse
import os
import sys
from datetime import datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--apply", action="store_true")
    p.add_argument("--beneficiaries", type=int, default=24)
    p.add_argument("--grantor", default="beta_staff")
    p.add_argument("--operator", default="beta_transport_operator")
    p.add_argument("--scan-count", type=int, default=12,
                   help="Controles AccessUse acceptes; pas de ScanLog Event pour le transport")
    a = p.parse_args(argv)
    if not 1 <= a.beneficiaries <= 100 or not 0 <= a.scan_count <= a.beneficiaries:
        p.error("Choisir 1..100 beneficiaires et 0..beneficiaries scans")
    import django
    django.setup()
    from django.contrib.auth import get_user_model
    from django.core.exceptions import ValidationError, PermissionDenied
    from django.db import connection, transaction
    from django.utils import timezone
    from activities.models import Activity, ActivityStatus, ActivityVisibility, Occurrence, OccurrenceStatus, OccurrencePlace, OccurrencePlaceRole
    from geography.models import Place
    from capacity.models import CapacityPool
    from capacity.services import reserve_capacity, commit_capacity
    from authorization.constants import SystemRoleCode
    from authorization.services import grant_activity_role
    from operations.permissions import user_can_manage_activity_operations
    from scanner.permissions import user_can_scan_activity
    from journeys.models import Journey, WorkflowKind
    from journeys.services import create_journey, submit_journey, confirm_journey
    from access.models import Access, AccessStatus, CredentialStatus
    from access.services import issue_access, validate_access
    from operations.checkpoint_models import OccurrenceCheckpoint, CheckpointStatus
    from operations.checkpoint_services import open_checkpoint
    from operations.queue_models import OccurrenceQueue, QueueEntry, QueueEligibilityPolicy, QueueStatus
    from operations.queue_services import enter_queue
    if connection.vendor != "sqlite":
        p.error("Demo autorisee uniquement avec SQLite")
    User = get_user_model()
    grantor = User.objects.filter(username=a.grantor, is_active=True).first()
    operator = User.objects.filter(username=a.operator, is_active=True,
        is_staff=False, is_superuser=False).first()
    if grantor is None or operator is None:
        p.error("Grantor ou operateur non administrateur introuvable")
    people = list(User.objects.filter(username__startswith="world_", is_active=True,
        is_staff=False,is_superuser=False).order_by("username")[:a.beneficiaries])
    if not people:
        p.error("Aucun beneficiaire world_")
    tz = ZoneInfo("Africa/Lubumbashi")
    now = timezone.now()
    local = now.astimezone(tz)
    tonight = datetime.combine(local.date(), time(20,0), tzinfo=tz)
    if tonight <= local:
        tonight += timedelta(days=1)
    tomorrow = datetime.combine(local.date()+timedelta(days=1), time(8,0), tzinfo=tz)
    if tomorrow <= local:
        tomorrow += timedelta(days=1)
    windows = [
        ("en-cours", now-timedelta(minutes=20), timedelta(hours=3)),
        ("ce-soir", tonight, timedelta(hours=5)),
        ("demain-matin", tomorrow, timedelta(hours=4)),
    ]
    slug = "demo-transport-lubumbashi-kolwezi"
    existing = Activity.objects.filter(slug=slug).first()
    if existing and existing.owner_profile_id != operator.pk:
        p.error("Une Activity de meme slug est possedee par un autre sujet")
    if existing and not user_can_manage_activity_operations(grantor, existing):
        p.error("Le grantor ne peut pas gerer cette Activity")
    print("SCENARIO: Navette demo Lubumbashi vers Kolwezi |", len(people), "beneficiaires")
    for label, start, duration in windows:
        print(" ", label, ":", start.astimezone(tz).isoformat(), "fin:",
              (start+duration).astimezone(tz).isoformat())
    if not a.apply:
        print("APERCU. Ajouter --apply pour ecrire les donnees demo, sans backup.")
        return
    with transaction.atomic():
        activity = existing
        if activity is None:
            activity = Activity(
                owner_profile=operator, created_by=grantor,
                title="[DEMO] Navette Lubumbashi - Kolwezi",
                slug=slug, short_description="Voyage fictif pour tester Jour J et les operations.",
                description="Depart de demonstration non commercial; aucun transport reel.",
                status=ActivityStatus.PUBLISHED, visibility=ActivityVisibility.PUBLIC)
            activity.full_clean()
            activity.save()
        for role in (SystemRoleCode.ACTIVITY_OPERATIONS_MANAGER, SystemRoleCode.ACTIVITY_SCANNER):
            grant_activity_role(profile=operator,activity=activity,role_code=role,
                granted_by=grantor,source="makolo-demo-transport")
        made = {"occurrences":0,"journeys":0,"accesses":0,"queue_entries":0,"accepted":0,"capacity_pools":0,"seat_reservations":0,"places":0}
        for label, start, duration in windows:
            # La cle datee empeche de reprogrammer un depart ayant deja des passages.
            key = "DEMO " + start.astimezone(tz).date().isoformat() + " " + label
            occurrence = Occurrence.objects.filter(activity=activity,label=key).first()
            if occurrence is None:
                occurrence = Occurrence(
                    activity=activity,label=key,start_at=start,end_at=start+duration,
                    timezone="Africa/Lubumbashi",status=OccurrenceStatus.SCHEDULED)
                occurrence.save()
                made["occurrences"] += 1
            origin = Place.objects.filter(is_active=True, country_code="CD").filter(
                locality__icontains="Lubumbashi").order_by("id").first()
            destination = Place.objects.filter(is_active=True, country_code="CD").filter(
                locality__icontains="Kolwezi").order_by("id").first()
            for place, role, position in (
                (origin, OccurrencePlaceRole.MEETING_POINT, 0),
                (destination, OccurrencePlaceRole.SERVICE_POINT, 1),
            ):
                if place is not None:
                    link, created = OccurrencePlace.objects.get_or_create(
                        occurrence=occurrence, place=place, role=role,
                        defaults={"position":position})
                    made["places"] += int(created)
            pool, created = CapacityPool.objects.get_or_create(
                source_key="makolo-demo-transport:"+str(occurrence.pk),
                defaults={"activity":activity, "occurrence":occurrence,
                          "label":"Sieges de demo", "total_quantity":max(100,a.beneficiaries)})
            made["capacity_pools"] += int(created)
            for person in people:
                journey = Journey.objects.filter(activity=activity,occurrence=occurrence,
                    beneficiary=person,workflow=WorkflowKind.RESERVATION).exclude(
                    status__in=["cancelled","expired","rejected"]).first()
                if journey is None:
                    try:
                        with transaction.atomic():
                            journey = create_journey(
                                initiated_by=person,beneficiary=person,activity=activity,
                                occurrence=occurrence,workflow=WorkflowKind.RESERVATION)
                            submit_journey(journey=journey,actor=person,reason="demo_transport")
                            confirm_journey(journey=journey,actor=person,reason="demo_transport")
                            made["journeys"] += 1
                    except ValidationError:
                        continue
                reservation = reserve_capacity(pool=pool, journey=journey,
                    quantity=1, source_key="makolo-demo-transport-seat")
                if reservation.status != "committed":
                    commit_capacity(reservation=reservation)
                    made["seat_reservations"] += 1
                access = Access.objects.filter(journey=journey,source_key="makolo-demo-transport").first()
                if access is None:
                    access = issue_access(beneficiary=person,activity=activity,
                        occurrence=occurrence,journey=journey,issued_by=operator,
                        source_key="makolo-demo-transport",audit_reason="demo_transport")
                    made["accesses"] += 1
            if not (occurrence.start_at <= now < occurrence.end_at):
                continue
            checkpoint, created = OccurrenceCheckpoint.objects.get_or_create(
                occurrence=occurrence,key="embarquement-demo",
                defaults={"label":"Embarquement demo", "status":CheckpointStatus.PLANNED})
            if checkpoint.status == CheckpointStatus.PLANNED:
                checkpoint = open_checkpoint(actor=operator,checkpoint=checkpoint)
            if checkpoint.status != CheckpointStatus.OPEN or not checkpoint.active:
                continue
            queue, created = OccurrenceQueue.objects.get_or_create(
                occurrence=occurrence,key="embarquement-demo",
                defaults={"checkpoint":checkpoint,"label":"File embarquement demo",
                          "eligibility_policy":QueueEligibilityPolicy.ACCESS_REQUIRED})
            if queue.status != QueueStatus.OPEN:
                continue
            for person in people:
                if not Access.objects.filter(occurrence=occurrence,beneficiary=person).exists():
                    continue
                before = QueueEntry.objects.filter(queue=queue,profile=person,
                    status__in=["waiting","called"]).exists()
                enter_queue(actor=operator,queue=queue,profile=person,
                    source="makolo-demo-transport",client_reference=str(person.pk)[:64])
                made["queue_entries"] += int(not before)
            if not user_can_scan_activity(operator,activity,occurrence=occurrence):
                raise PermissionDenied("L'operateur n'a pas d'autorite Scanner pour cette Activity")
            for person in people[:a.scan_count]:
                access = Access.objects.filter(occurrence=occurrence,beneficiary=person,
                    source_key="makolo-demo-transport",status=AccessStatus.VALID).first()
                if not access:
                    continue
                cred = access.credentials.filter(status=CredentialStatus.ACTIVE).order_by("-version").first()
                if not cred:
                    continue
                result = validate_access(
                    access=access,credential=cred,controller=operator,
                    authority_check=lambda user, right: user_can_scan_activity(
                        user,right.activity,occurrence=right.occurrence),
                    expected_activity=activity,expected_occurrence=occurrence,
                    source="makolo-demo-transport",client_reference="demo-"+access.pk.hex)
                made["accepted"] += int(result.accepted)
        print("CREATIONS:",made)
    print("Les passages transport sont AccessUse (pas des ScanLog Event).")


if __name__ == "__main__":
    main()
