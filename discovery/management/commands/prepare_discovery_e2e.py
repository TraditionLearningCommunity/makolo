from datetime import datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from accounts.models import User
from activities.models import (
    Activity,
    ActivityStatus,
    ActivityVisibility,
    Occurrence,
    OccurrencePlace,
    OccurrencePlaceRole,
    OccurrenceStatus,
)
from capacity.models import CapacityPool
from commerce.models import Offer, OfferStatus, PaymentMode
from events.models import Event, EventCategory
from geography.models import Place
from organizations.models import Organization
from transport.models import TransportService
from transport.services import (
    configure_transport_fare,
    create_transport_departure,
    publish_transport_departure,
)


TZ = ZoneInfo("Africa/Lubumbashi")


class Command(BaseCommand):
    help = "Prepare clock-relative, multi-vertical Discovery fixtures for Playwright."

    def handle(self, *args, **options):
        if not getattr(settings, "IS_E2E", False):
            raise CommandError("prepare_discovery_e2e est réservé à DJANGO_ENV=e2e.")

        owner = User.objects.get(username="e2e-owner")
        event_space = Organization.objects.get(name="Makolo E2E Events")
        event_place = Place.objects.get(name="Centre Makolo E2E")
        event_place.latitude = Decimal("-11.664700")
        event_place.longitude = Decimal("27.479400")
        event_place.timezone = "Africa/Lubumbashi"
        event_place.save(update_fields=["latitude", "longitude", "timezone", "updated_at"])

        tomorrow = timezone.localdate() + timedelta(days=1)
        event_start = datetime.combine(tomorrow, time(17, 30), tzinfo=TZ)
        event_end = event_start + timedelta(hours=3)
        category = EventCategory.objects.get(name="Culture E2E")
        activity = Activity.objects.create(
            space=event_space,
            created_by=owner,
            title="Discovery Event E2E",
            short_description="Événement public créé relativement à l’horloge E2E.",
            status=ActivityStatus.PUBLISHED,
            visibility=ActivityVisibility.PUBLIC,
        )
        occurrence = Occurrence.objects.create(
            activity=activity,
            label="Soirée Discovery E2E",
            start_at=event_start,
            end_at=event_end,
            timezone="Africa/Lubumbashi",
            status=OccurrenceStatus.SCHEDULED,
        )
        OccurrencePlace.objects.create(
            occurrence=occurrence,
            place=event_place,
            role=OccurrencePlaceRole.PRIMARY,
        )
        Event.objects.create(activity=activity, category=category, published_at=timezone.now())
        pool = CapacityPool.objects.create(
            activity=activity,
            occurrence=occurrence,
            label="Entrées Discovery E2E",
            total_quantity=40,
        )
        Offer.objects.create(
            activity=activity,
            occurrence=occurrence,
            capacity_pool=pool,
            name="Inscription Discovery E2E",
            unit_price=Decimal("0.00"),
            currency="USD",
            payment_mode=PaymentMode.NONE,
            status=OfferStatus.ACTIVE,
        )

        origin = Place.objects.get(name="Agence Mulykap Lubumbashi E2E")
        destination = Place.objects.get(name="Agence Mulykap Kolwezi E2E")
        origin.latitude = Decimal("-11.660800")
        origin.longitude = Decimal("27.479900")
        origin.timezone = "Africa/Lubumbashi"
        origin.save(update_fields=["latitude", "longitude", "timezone", "updated_at"])
        destination.latitude = Decimal("-10.716700")
        destination.longitude = Decimal("25.466700")
        destination.timezone = "Africa/Lubumbashi"
        destination.save(update_fields=["latitude", "longitude", "timezone", "updated_at"])

        service = TransportService.objects.get(activity__title="Lubumbashi → Kolwezi E2E")
        departure_start = datetime.combine(tomorrow, time(8, 0), tzinfo=TZ)
        departure = create_transport_departure(
            service=service,
            start_at=departure_start,
            end_at=departure_start + timedelta(hours=4),
            timezone_name="Africa/Lubumbashi",
            capacity=24,
            operational_reference="E2E-DISCOVERY-TOMORROW",
        )
        configure_transport_fare(
            departure=departure,
            name="Tarif Discovery E2E",
            unit_price=Decimal("18.00"),
            payment_mode=PaymentMode.UPFRONT,
        )
        publish_transport_departure(departure=departure)

        for title, visibility in (
            ("Discovery Unlisted E2E", ActivityVisibility.UNLISTED),
            ("Discovery Private E2E", ActivityVisibility.PRIVATE),
        ):
            hidden = Activity.objects.create(
                space=event_space,
                created_by=owner,
                title=title,
                status=ActivityStatus.PUBLISHED,
                visibility=visibility,
            )
            hidden_occurrence = Occurrence.objects.create(
                activity=hidden,
                start_at=event_start,
                end_at=event_end,
                timezone="Africa/Lubumbashi",
                status=OccurrenceStatus.SCHEDULED,
            )
            OccurrencePlace.objects.create(
                occurrence=hidden_occurrence,
                place=event_place,
                role=OccurrencePlaceRole.PRIMARY,
            )

        self.stdout.write(self.style.SUCCESS("Discovery E2E fixtures ready."))
