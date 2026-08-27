from datetime import timedelta

from django.db.models import Count, DecimalField, IntegerField, Min, OuterRef, Q, Subquery, Value
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.utils.dateparse import parse_date

from commerce.models import OfferStatus
from events.models import Event, EventStatus, EventVisibility
from organizations.models import OrganizationFollow, OrganizationVerificationStatus
from tickets.models import TicketOrder, TicketOrderStatus, TicketType

from .models import ActivityBookmark


RECENT_DAYS = 30


def _count_for_event(queryset):
    return (
        queryset.order_by()
        .values("event_id")
        .annotate(total=Count("pk"))
        .values("total")[:1]
    )


def _public_event_annotations():
    min_ticket_price = (
        TicketType.objects.filter(
            event_id=OuterRef("pk"),
            offer__status=OfferStatus.ACTIVE,
            capacity_pool__is_active=True,
        )
        .order_by()
        .values("event_id")
        .annotate(value=Min("offer__unit_price"))
        .values("value")[:1]
    )
    bookmark_count = (
        ActivityBookmark.objects.filter(activity_id=OuterRef("activity_id"))
        .order_by()
        .values("activity_id")
        .annotate(total=Count("pk"))
        .values("total")[:1]
    )
    confirmed_order_count = _count_for_event(
        TicketOrder.objects.filter(
            event_id=OuterRef("pk"),
            status=TicketOrderStatus.CONFIRMED,
        )
    )
    return {
        "min_ticket_price": Subquery(
            min_ticket_price,
            output_field=DecimalField(max_digits=12, decimal_places=2),
        ),
        "bookmark_count": Coalesce(
            Subquery(bookmark_count, output_field=IntegerField()),
            Value(0),
        ),
        "confirmed_order_count": Coalesce(
            Subquery(confirmed_order_count, output_field=IntegerField()),
            Value(0),
        ),
    }


def public_discovery_events():
    now = timezone.now()
    return (
        Event.objects.select_related(
            "activity",
            "activity__space",
            "activity__owner_profile",
            "category",
            "venue",
            "venue__place",
        )
        .prefetch_related("activity__occurrences")
        .filter(
            activity__status=EventStatus.PUBLISHED,
            activity__visibility=EventVisibility.PUBLIC,
            activity__occurrences__end_at__gte=now,
        )
        .exclude(
            activity__space__verification_status=OrganizationVerificationStatus.SUSPENDED
        )
        .annotate(**_public_event_annotations())
    )


def search_discovery_events(params):
    """Legacy Event-specific query retained for API compatibility.

    New Discovery surfaces use search_occurrences(); this function remains only
    for callers whose public contract is explicitly Event-shaped.
    """
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
            Q(activity__title__icontains=q)
            | Q(activity__short_description__icontains=q)
            | Q(activity__description__icontains=q)
            | Q(activity__space__name__icontains=q)
            | Q(activity__owner_profile__first_name__icontains=q)
            | Q(activity__owner_profile__last_name__icontains=q)
            | Q(category__name__icontains=q)
            | Q(venue__name__icontains=q)
            | Q(venue__place__locality__icontains=q)
        )
    if category:
        queryset = queryset.filter(Q(category__slug=category) | Q(category__name__iexact=category))
    if city:
        queryset = queryset.filter(
            Q(venue__place__locality__icontains=city)
            | Q(activity__space__city__icontains=city)
        )
    if organizer:
        queryset = queryset.filter(
            Q(activity__space__slug=organizer)
            | Q(activity__space__name__icontains=organizer)
            | Q(activity__owner_profile__username__iexact=organizer)
        )
    if price == "free":
        queryset = queryset.filter(
            ticket_types__offer__status=OfferStatus.ACTIVE,
            ticket_types__capacity_pool__is_active=True,
            ticket_types__offer__unit_price=0,
        )
    elif price == "paid":
        queryset = queryset.filter(
            ticket_types__offer__status=OfferStatus.ACTIVE,
            ticket_types__capacity_pool__is_active=True,
            ticket_types__offer__unit_price__gt=0,
        )
    if date_from:
        queryset = queryset.filter(activity__occurrences__start_at__date__gte=date_from)
    if date_to:
        queryset = queryset.filter(activity__occurrences__start_at__date__lte=date_to)

    ordering = (params.get("ordering") or "upcoming").strip().lower()
    if ordering == "newest":
        queryset = queryset.order_by(
            "-published_at",
            "-created_at",
            "activity__occurrences__start_at",
        )
    elif ordering == "popular":
        queryset = queryset.order_by(
            "-confirmed_order_count",
            "-bookmark_count",
            "activity__occurrences__start_at",
        )
    else:
        queryset = queryset.order_by(
            "activity__occurrences__start_at",
            "activity__title",
        )
    return queryset.distinct()


def _event_score(event, *, followed_org_ids, preferred_category_ids, preferred_cities):
    score = 0
    reasons = []
    if event.organization_id in followed_org_ids:
        score += 60
        reasons.append(f"Parce que vous suivez {event.organization.name}")
    if event.category_id and event.category_id in preferred_category_ids:
        score += 30
        reasons.append(f"Parce que vous avez enregistré des événements {event.category.name}")
    venue_city = event.venue.effective_city if event.venue_id else ""
    organization_city = event.organization.city if event.organization_id else ""
    event_city = (venue_city or organization_city or "").strip().lower()
    if event_city and event_city in preferred_cities:
        score += 18
        reasons.append(f"Près de vous à {venue_city or organization_city}")
    score += min(getattr(event, "confirmed_order_count", 0), 20) * 3
    score += min(getattr(event, "bookmark_count", 0), 20) * 2
    days_until = max((event.start_at - timezone.now()).days, 0)
    score += max(20 - min(days_until, 20), 0)
    if not reasons:
        if getattr(event, "confirmed_order_count", 0) or getattr(event, "bookmark_count", 0):
            reasons.append("Activité demandée en ce moment")
        else:
            reasons.append("À venir sur Makolo")
    return score, reasons[:2]


def _profile_city(user):
    try:
        return (user.profile.city or "").strip().lower()
    except Exception:
        return ""


def build_recommendations(user, *, limit=12):
    """Compatibility recommendations currently limited to the Event vertical.

    The universal findability surface is Activity/Occurrence-first Discovery.
    This compatibility section intentionally keeps its legacy Event-shaped
    return contract until a future recommendation contract becomes generic.
    """
    candidates = list(
        public_discovery_events().order_by("activity__occurrences__start_at")[:120]
    )
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
        ActivityBookmark.objects.filter(
            user=user,
            activity__event_vertical__category__isnull=False,
        ).values_list("activity__event_vertical__category_id", flat=True)
    )
    preferred_category_ids = purchased_category_ids | bookmarked_category_ids
    preferred_cities = set(
        value.strip().lower()
        for value in TicketOrder.objects.filter(
            buyer=user,
            status=TicketOrderStatus.CONFIRMED,
            event__venue__place__locality__gt="",
        ).values_list("event__venue__place__locality", flat=True)
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
    recent_orders = _count_for_event(
        TicketOrder.objects.filter(
            event_id=OuterRef("pk"),
            status=TicketOrderStatus.CONFIRMED,
            confirmed_at__gte=cutoff,
        )
    )
    recent_bookmarks = (
        ActivityBookmark.objects.filter(
            activity_id=OuterRef("activity_id"),
            created_at__gte=cutoff,
        )
        .order_by()
        .values("activity_id")
        .annotate(total=Count("pk"))
        .values("total")[:1]
    )
    events = list(
        public_discovery_events()
        .annotate(
            recent_orders=Coalesce(
                Subquery(recent_orders, output_field=IntegerField()),
                Value(0),
            ),
            recent_bookmarks=Coalesce(
                Subquery(recent_bookmarks, output_field=IntegerField()),
                Value(0),
            ),
        )
        .order_by("activity__occurrences__start_at")[:120]
    )
    rows = []
    now = timezone.now()
    for event in events:
        days_until = max((event.start_at - now).days, 0)
        score = (
            event.recent_orders * 8
            + event.recent_bookmarks * 4
            + max(14 - min(days_until, 14), 0)
        )
        rows.append({"event": event, "score": score})
    return sorted(rows, key=lambda row: (-row["score"], row["event"].start_at))[:limit]


def serialize_event(event, *, reason=None, score=None):
    venue_city = event.venue.effective_city if event.venue_id else ""
    organization_city = event.organization.city if event.organization_id else ""
    return {
        "id": str(event.pk),
        "slug": event.slug,
        "title": event.title,
        "short_description": event.short_description,
        "start_at": event.start_at,
        "end_at": event.end_at,
        "category": event.category.name if event.category_id else None,
        "city": venue_city or organization_city,
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
