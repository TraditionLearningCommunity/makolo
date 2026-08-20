import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


class TransportMode(models.TextChoices):
    ROAD = "road", "Route"
    AIR = "air", "Air"
    RAIL = "rail", "Rail"
    WATER = "water", "Eau"
    OTHER = "other", "Autre"


class VehicleType(models.TextChoices):
    BUS = "bus", "Bus / autocar"
    MINIBUS = "minibus", "Minibus"
    VAN = "van", "Van"
    CAR = "car", "Voiture"
    OTHER = "other", "Autre"


class TransportRoute(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    space = models.ForeignKey("organizations.Organization", on_delete=models.PROTECT, related_name="transport_routes")
    code = models.CharField(max_length=48, blank=True)
    name = models.CharField(max_length=180)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name", "id"]
        indexes = [models.Index(fields=["space", "active"], name="transport_route_space_idx")]
        constraints = [models.UniqueConstraint(fields=["space", "code"], condition=~Q(code=""), name="transport_route_code_unique")]

    @property
    def origin(self):
        links = list(self.stops.all())
        return links[0].place if links else None

    @property
    def destination(self):
        links = list(self.stops.all())
        return links[-1].place if links else None

    def __str__(self):
        return self.name


class TransportRouteStop(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    route = models.ForeignKey(TransportRoute, on_delete=models.CASCADE, related_name="stops")
    place = models.ForeignKey("geography.Place", on_delete=models.PROTECT, related_name="transport_route_stops")
    position = models.PositiveSmallIntegerField()
    boarding_allowed = models.BooleanField(default=True)
    alighting_allowed = models.BooleanField(default=True)
    notes = models.CharField(max_length=320, blank=True)

    class Meta:
        ordering = ["position", "id"]
        constraints = [
            models.CheckConstraint(condition=Q(position__gte=1), name="transport_stop_position_positive"),
            models.UniqueConstraint(fields=["route", "position"], name="transport_route_stop_position_unique"),
        ]
        indexes = [models.Index(fields=["route", "position"], name="transport_stop_route_idx")]


class TransportService(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    activity = models.OneToOneField("activities.Activity", on_delete=models.CASCADE, related_name="transport_service")
    route = models.ForeignKey(TransportRoute, on_delete=models.PROTECT, related_name="services")
    mode = models.CharField(max_length=16, choices=TransportMode.choices, default=TransportMode.ROAD)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        super().clean()
        if self.activity_id and self.route_id and self.activity.space_id != self.route.space_id:
            raise ValidationError({"route": "La Route et l’Activity doivent appartenir au même Espace."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class Vehicle(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    space = models.ForeignKey("organizations.Organization", on_delete=models.PROTECT, related_name="transport_vehicles")
    label = models.CharField(max_length=180)
    registration = models.CharField(max_length=80, blank=True)
    vehicle_type = models.CharField(max_length=16, choices=VehicleType.choices, default=VehicleType.BUS)
    passenger_capacity = models.PositiveIntegerField()
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["label", "id"]
        indexes = [models.Index(fields=["space", "active"], name="transport_vehicle_space_idx")]
        constraints = [models.CheckConstraint(condition=Q(passenger_capacity__gt=0), name="transport_vehicle_capacity_positive")]

    def __str__(self):
        return self.label


class TransportDeparture(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    occurrence = models.OneToOneField("activities.Occurrence", on_delete=models.CASCADE, related_name="transport_departure")
    vehicle = models.ForeignKey(Vehicle, on_delete=models.PROTECT, related_name="departures", null=True, blank=True)
    passenger_capacity_pool = models.OneToOneField("capacity.CapacityPool", on_delete=models.PROTECT, related_name="transport_departure")
    boarding_instructions = models.CharField(max_length=320, blank=True)
    operational_reference = models.CharField(max_length=80, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["vehicle"], name="transport_depart_vehicle_idx")]

    def clean(self):
        super().clean()
        errors = {}
        if self.occurrence_id:
            try:
                service = self.occurrence.activity.transport_service
            except Exception:
                errors["occurrence"] = "L’Occurrence doit appartenir à une Activity Transport."
                service = None
            if self.vehicle_id and service and self.vehicle.space_id != service.route.space_id:
                errors["vehicle"] = "Le véhicule doit appartenir au même Espace que le service Transport."
        if self.passenger_capacity_pool_id and self.occurrence_id:
            pool = self.passenger_capacity_pool
            if pool.activity_id != self.occurrence.activity_id or pool.occurrence_id != self.occurrence_id:
                errors["passenger_capacity_pool"] = "La CapacityPool doit cibler l’Activity et l’Occurrence de ce départ."
            if self.vehicle_id and pool.total_quantity is not None and pool.total_quantity > self.vehicle.passenger_capacity:
                errors["passenger_capacity_pool"] = "La capacité vendable dépasse la capacité physique du véhicule."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)
