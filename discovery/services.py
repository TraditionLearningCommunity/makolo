from datetime import timedelta

from django.db.models import Count, Min, Q
from django.utils import timezone
from django.utils.dateparse import parse_date

from events.models import Event, EventStatus, EventVisibility
from organizations.models import OrganizationFollow, OrganizationVerificationStatus
from tickets.models import TicketOrder, TicketOrderStatus

from .models import EventBookmark


RECENT_DAYS = 30


def public_discovery_events():
    now = timezone.now()
    return (
        Event.objects.select_related("organization", "category", "venue")
        .filter(
            status=EventStatus.PUBLISHED,
            visibility=EventVisibility.PUBLIC,
            end_at__gte=now,
        )
        .exclude(
            organization__verification_status=OrganizationVerificationStatus.SUSPENDED
        )
        .annotate(
            min_ticket_price=Min("ticket_types__price", filter=Q(ticket_types__is_active=True)),
            bookmark_count=Count("bookmarks", distinct=True),
            confirmed_order_count=Count(
                "ticket_orders",
                filter=Q(ticket_orders__status=TicketOrderStatus.CONFIRMED),
                distinct=True,
            ),
            follower_count=Count("organization__followers", distinct=True),
        )
    )


def search_discovery_events(params):
    queryset = public_discovery_events()
    q = (params.get("q") or "").strip()
    category = (params.get("category") or "").strip()
    city = (params.get("city") or "").strip()
    organizer = (params.get("organizer") or "").strip()
    price = (params.get("price") or "").strip().lower()
    date_from = parse_date((params.get("date_from") or "").strip())
    date_to = parse_date((params.get("date_to") or "").strip())

    if q:
        queryset = queryset.filter(
            Q(title__icontains=q)
            | Q(short_description__icontains=q)
            | Q(description__icontains=q)
            | Q(organization__name__icontains=q)
            | Q(category__name__icontains=q)
            | Q(venue__name__icontains=q)
            | Q(venue__city__icontains=q)
        )
    if category:
        queryset = queryset.filter(Q(category__slug=category) | Q(category__name__iexact=category))
    if city:
        queryset = queryset.filter(Q(venue__city__icontains=city) | Q(organization__city__icontains=city))
    if organizer:
        queryset = queryset.filter(
            Q(organization__slug=organizer) | Q(organization__name__icontains=organizer)
        )
    if price == "free":
        queryset = queryset.filter(ticket_types__is_active=True, ticket_types__price=0)
    elif price == "paid":
        queryset = queryset.filter(ticket_types__is_active=True, ticket_types__price__gt=0)
    if date_from:
        queryset = queryset.filter(start_at__date__gte=date_from)
    if date_to:
        queryset = queryset.filter(start_at__date__lte=date_to)

    ordering = (params.get("ordering") or "upcoming").strip().lower()
    if ordering == "newest":
        queryset = queryset.order_by("-published_at", "-created_at", "start_at")
    elif ordering == "popular":
        queryset = queryset.order_by(
            "-confirmed_order_count", "-bookmark_count", "-follower_count", "start_at"
        )
    else:
        queryset = queryset.order_by("start_at", "title")
    return queryset.distinct()


def _event_score(event, *, followed_org_ids, preferred_category_ids, preferred_cities):
    score = 0
    reasons = []
    if event.organization_id in followed_org_ids:
        score += 60
        reasons.append(f"Parce que vous suivez {event.organization.name}")
    if event.category_id and event.category_id in preferred_category_ids:
        score += 30
        reasons.append(f"Parce que vous aimez les événements {event.category.name}")
    event_city = (getattr(event.venue, "city", "") or getattr(event.organization, "city", "") or "").strip().lower()
    if event_city and event_city in preferred_cities:
        score += 18
        reasons.append(f"Près de vous à {getattr(event.venue, 'city', '') or event.organization.city}")
    score += min(getattr(event, "confirmed_order_count", 0), 20) * 3
    score += min(getattr(event, "bookmark_count", 0), 20) * 2
    score += min(getattr(event, "follower_count", 0), 50)
    days_until = max((event.start_at - timezone.now()).days, 0)
    score += max(20 - min(days_until, 20), 0)
    if not reasons:
        if getattr(event, "confirmed_order_count", 0) or getattr(event, "bookmark_count", 0):
            reasons.append("Populaire en ce moment")
        else:
            reasons.append("À venir sur Makolo")
    return score, reasons[:2]


def _profile_city(user):
    try:
        return (user.profile.city or "").strip().lower()
    except Exception:
        return ""


def build_recommendations(user, *, limit=12):
    candidates = list(public_discovery_events().order_by("start_at")[:120])
    if not getattr(user, "is_authenticated", False):
        ranked = []
        for event in candidates:
            score, reasons = _event_score(
                event,
                followed_org_ids=set(),
                preferred_category_ids=set(),
                preferred_cities=set(),
            )
            ranked.append({"event": event, "score": score, "reasons": reasons})
        return sorted(ranked, key=lambda row: (-row["score"], row["event"].start_at))[:limit]

    followed_org_ids = set(
        OrganizationFollow.objects.filter(user=user).values_list("organization_id", flat=True)
    )
    purchased_category_ids = set(
        TicketOrder.objects.filter(
            buyer=user,
            status=TicketOrderStatus.CONFIRMED,
            event__category__isnull=False,
        ).values_list("event__category_id", flat=True)
    )
    bookmarked_category_ids = set(
        EventBookmark.objects.filter(user=user, event__category__isnull=False).values_list(
            "event__category_id", flat=True
        )
    )
    preferred_category_ids = purchased_category_ids | bookmarked_category_ids
    preferred_cities = set(
        value.strip().lower()
        for value in TicketOrder.objects.filter(
            buyer=user,
            status=TicketOrderStatus.CONFIRMED,
            event__venue__city__gt="",
        ).values_list("event__venue__city", flat=True)
        if value
    )
    city = _profile_city(user)
    if city:
        preferred_cities.add(city)

    already_owned_event_ids = set(
        TicketOrder.objects.filter(
            buyer=user,
            status=TicketOrderStatus.CONFIRMED,
        ).values_list("event_id", flat=True)
    )
    ranked = []
    for event in candidates:
        if event.pk in already_owned_event_ids:
            continue
        score, reasons = _event_score(
            event,
            followed_org_ids=followed_org_ids,
            preferred_category_ids=preferred_category_ids,
            preferred_cities=preferred_cities,
        )
        ranked.append({"event": event, "score": score, "reasons": reasons})
    return sorted(ranked, key=lambda row: (-row["score"], row["event"].start_at))[:limit]


def build_trending(*, limit=10):
    cutoff = timezone.now() - timedelta(days=RECENT_DAYS)
    events = list(
        public_discovery_events()
        .annotate(
            recent_orders=Count(
                "ticket_orders",
                filter=Q(
                    ticket_orders__status=TicketOrderStatus.CONFIRMED,
                    ticket_orders__confirmed_at__gte=cutoff,
                ),
                distinct=True,
            ),
            recent_bookmarks=Count(
                "bookmarks",
                filter=Q(bookmarks__created_at__gte=cutoff),
                distinct=True,
            ),
        )
        .order_by("start_at")[:120]
    )
    rows = []
    now = timezone.now()
    for event in events:
        days_until = max((event.start_at - now).days, 0)
        score = (
            event.recent_orders * 8
            + event.recent_bookmarks * 4
            + min(event.follower_count, 50)
            + max(14 - min(days_until, 14), 0)
        )
        rows.append({"event": event, "score": score})
    return sorted(rows, key=lambda row: (-row["score"], row["event"].start_at))[:limit]


def serialize_event(event, *, reason=None, score=None):
    return {
        "id": str(event.pk),
        "slug": event.slug,
        "title": event.title,
        "short_description": event.short_description,
        "start_at": event.start_at,
        "end_at": event.end_at,
        "category": event.category.name if event.category_id else None,
        "city": (event.venue.city if event.venue_id else "") or (event.organization.city if event.organization_id else ""),
        "organization": (
            {"slug": event.organization.slug, "name": event.organization.name}
            if event.organization_id
            else None
        ),
        "min_ticket_price": getattr(event, "min_ticket_price", None),
        "bookmark_count": getattr(event, "bookmark_count", 0),
        "confirmed_order_count": getattr(event, "confirmed_order_count", 0),
        "reason": reason,
        "score": score,
    }
