from datetime import timedelta

from django.conf import settings
from django.core.management import BaseCommand, CommandError
from django.utils import timezone

from access.models import Access, AccessStatus
from accounts.models import User
from activities.models import Activity, ActivityStatus, Occurrence, OccurrencePlace, OccurrencePlaceRole, OccurrenceStatus
from geography.models import Place
from journeys.models import Journey, JourneyStatus, WorkflowKind
from operations.models import (
    CheckpointStatus,
    OccurrenceCheckpoint,
    OccurrenceQueue,
    PlacementAssignment,
    PlacementPlan,
    PlacementUnit,
    QueueEntry,
    QueueEntryStatus,
)

from .prepare_e2e import E2E_PASSWORD


class Command(BaseCommand):
    help = "Prepare isolated M8-C Journey to real-world action browser fixtures."

    def handle(self, *args, **options):
        if not getattr(settings, "IS_E2E", False):
            raise CommandError("prepare_m8c_e2e est réservé à DJANGO_ENV=e2e.")

        now = timezone.now()
        owner = User.objects.get(email="owner@e2e.makolo.test")
        participant = User.objects.create_user(
            email="m8c.participant@e2e.makolo.test",
            username="e2e-m8c-participant",
            password=E2E_PASSWORD,
        )
        place = Place.objects.create(
            name="Maison de l’action E2E",
            address_line="88 avenue du Réel",
            locality="Lubumbashi",
            country_code="CD",
            timezone="Africa/Lubumbashi",
            access_instructions="Présentez-vous à l’accueil principal.",
            latitude="-11.664700",
            longitude="27.479400",
            created_by=owner,
        )

        self._experience(
            owner=owner,
            participant=participant,
            place=place,
            title="M8-C préparation E2E",
            start_at=now + timedelta(hours=4),
            end_at=now + timedelta(hours=6),
        )
        departure = self._experience(
            owner=owner,
            participant=participant,
            place=place,
            title="M8-C départ E2E",
            start_at=now + timedelta(minutes=45),
            end_at=now + timedelta(hours=3),
        )
        OccurrenceCheckpoint.objects.create(
            occurrence=departure,
            key="arrival",
            label="Accueil principal",
            position=1,
            required=True,
            status=CheckpointStatus.OPEN,
        )

        live = self._experience(
            owner=owner,
            participant=participant,
            place=place,
            title="M8-C action réelle E2E",
            start_at=now - timedelta(minutes=5),
            end_at=now + timedelta(hours=2),
        )
        checkpoint = OccurrenceCheckpoint.objects.create(
            occurrence=live,
            key="live-desk",
            label="Guichet live",
            position=1,
            required=True,
            status=CheckpointStatus.OPEN,
        )
        plan = PlacementPlan.objects.create(
            occurrence=live,
            key="zone",
            label="Placement E2E",
            required=True,
        )
        zone = PlacementUnit.objects.create(plan=plan, key="zone-a", label="Zone A", kind="zone")
        place_unit = PlacementUnit.objects.create(plan=plan, parent=zone, key="place-7", label="Place 7", kind="seat")
        PlacementAssignment.objects.create(
            plan=plan,
            unit=place_unit,
            profile=participant,
            assigned_by=owner,
        )
        queue = OccurrenceQueue.objects.create(
            occurrence=live,
            checkpoint=checkpoint,
            key="live-desk",
            label="Guichet live",
        )
        QueueEntry.objects.create(
            queue=queue,
            profile=participant,
            sequence=1,
            status=QueueEntryStatus.CALLED,
            entered_by=participant,
            called_by=owner,
            called_at=now,
        )

        self._experience(
            owner=owner,
            participant=participant,
            place=place,
            title="M8-C fin E2E",
            start_at=now - timedelta(hours=3),
            end_at=now - timedelta(hours=1),
            occurrence_status=OccurrenceStatus.COMPLETED,
        )

    def _experience(
        self,
        *,
        owner,
        participant,
        place,
        title,
        start_at,
        end_at,
        occurrence_status=OccurrenceStatus.SCHEDULED,
    ):
        activity = Activity.objects.create(
            created_by=owner,
            title=title,
            status=ActivityStatus.PUBLISHED,
        )
        occurrence = Occurrence.objects.create(
            activity=activity,
            label=title,
            start_at=start_at,
            end_at=end_at,
            timezone="Africa/Lubumbashi",
            status=occurrence_status,
        )
        OccurrencePlace.objects.create(
            occurrence=occurrence,
            place=place,
            role=OccurrencePlaceRole.PRIMARY,
        )
        journey = Journey.objects.create(
            initiated_by=participant,
            beneficiary=participant,
            activity=activity,
            occurrence=occurrence,
            workflow=WorkflowKind.REGISTRATION,
            status=JourneyStatus.CONFIRMED,
        )
        Access.objects.create(
            beneficiary=participant,
            activity=activity,
            occurrence=occurrence,
            journey=journey,
            status=AccessStatus.VALID,
        )
        return occurrence