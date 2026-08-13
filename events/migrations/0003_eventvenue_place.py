import uuid
from decimal import Decimal

import django.db.models.deletion
from django.db import migrations, models


NAMESPACE = uuid.UUID("479d8b33-c9b0-47d2-a5f0-14a79eb96ead")
COUNTRY_CODES = {
    "rdc": "CD",
    "drc": "CD",
    "congo-kinshasa": "CD",
    "république démocratique du congo": "CD",
    "democratic republic of the congo": "CD",
    "kenya": "KE",
    "france": "FR",
    "belgique": "BE",
    "belgium": "BE",
}


def normalized_country_code(value):
    raw = (value or "").strip()
    if len(raw) == 2 and raw.isascii() and raw.isalpha():
        return raw.upper()
    return COUNTRY_CODES.get(raw.casefold(), "")


def safe_coordinates(latitude, longitude):
    if latitude is None or longitude is None:
        return None, None
    latitude = Decimal(latitude)
    longitude = Decimal(longitude)
    if not Decimal("-90") <= latitude <= Decimal("90"):
        return None, None
    if not Decimal("-180") <= longitude <= Decimal("180"):
        return None, None
    return latitude, longitude


def backfill_event_venue_places(apps, schema_editor):
    EventVenue = apps.get_model("events", "EventVenue")
    Place = apps.get_model("geography", "Place")
    for venue in EventVenue.objects.filter(kind__in=["physical", "hybrid"]).iterator():
        latitude, longitude = safe_coordinates(venue.latitude, venue.longitude)
        place_id = uuid.uuid5(NAMESPACE, f"event-venue:{venue.pk}")
        place, _ = Place.objects.update_or_create(
            id=place_id,
            defaults={
                "name": venue.name,
                "address_line": venue.address,
                "locality": venue.city,
                "administrative_area": "",
                "postal_code": "",
                "country_code": normalized_country_code(venue.country),
                "latitude": latitude,
                "longitude": longitude,
                "timezone": "",
                "access_instructions": "",
                "is_active": venue.is_active,
                "created_by_id": None,
            },
        )
        EventVenue.objects.filter(pk=venue.pk).update(place_id=place.pk)


def reverse_backfill(apps, schema_editor):
    EventVenue = apps.get_model("events", "EventVenue")
    EventVenue.objects.update(place_id=None)


class Migration(migrations.Migration):
    dependencies = [
        ("events", "0002_event_organization"),
        ("geography", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="eventvenue",
            name="place",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="event_venues",
                to="geography.place",
            ),
        ),
        migrations.RunPython(backfill_event_venue_places, reverse_backfill),
    ]
