from events.activity_bridge import sync_event_core
from events.models import VenueKind
from geography.models import Place

from .common import upsert


def _ensure_canonical_venue_place(event):
    venue = event.venue
    if venue is None or venue.kind not in {VenueKind.PHYSICAL, VenueKind.HYBRID}:
        return None
    if venue.place_id:
        return venue.place

    country_code = (venue.country or "").strip().upper()
    if len(country_code) != 2:
        country_code = ""
    place = upsert(
        Place,
        f"event-venue:{venue.pk}",
        defaults={
            "name": venue.name,
            "address_line": venue.address,
            "locality": venue.city,
            "country_code": country_code,
            "latitude": venue.latitude,
            "longitude": venue.longitude,
            "timezone": event.timezone or "",
            "is_active": venue.is_active,
            "created_by": event.organizer,
        },
    )
    venue.place = place
    venue.save(update_fields=["place", "updated_at"])
    return place


def seed_activity_core(ctx):
    projected = 0
    for event in ctx.events:
        _ensure_canonical_venue_place(event)
        sync_event_core(event)
        projected += 1
    ctx.add("activity_core_projections", projected)
