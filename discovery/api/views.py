from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from discovery.models import EventBookmark
from discovery.search import search_occurrences
from discovery.services import (
    build_recommendations,
    build_trending,
    public_discovery_events,
    serialize_event,
)


DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 50
MAX_MAP_POINTS = 100


def _page_params(params):
    try:
        page = max(int(params.get("page") or 1), 1)
        page_size = min(max(int(params.get("page_size") or DEFAULT_PAGE_SIZE), 1), MAX_PAGE_SIZE)
    except (TypeError, ValueError) as exc:
        raise ValidationError("Pagination invalide.") from exc
    return page, page_size


class DiscoveryItemsAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        try:
            result = search_occurrences(request.query_params)
            page, page_size = _page_params(request.query_params)
        except ValidationError as exc:
            return Response({"errors": exc.messages}, status=400)
        start = (page - 1) * page_size
        end = start + page_size
        return Response(
            {
                "count": result.total,
                "page": page,
                "page_size": page_size,
                "timezone": result.timezone_name,
                "results": [item.to_public_dict() for item in result.items[start:end]],
            }
        )


class DiscoveryMapAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        try:
            result = search_occurrences(request.query_params)
        except ValidationError as exc:
            return Response({"errors": exc.messages}, status=400)
        points = []
        for item in result.items:
            payload = item.to_map_dict()
            if payload is not None:
                points.append(payload)
            if len(points) >= MAX_MAP_POINTS:
                break
        return Response(
            {
                "count": len(points),
                "total_results": result.total,
                "timezone": result.timezone_name,
                "results": points,
            }
        )


class DiscoveryForYouAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        recommendations = build_recommendations(request.user, limit=24)
        trending = build_trending(limit=12)
        return Response(
            {
                "recommendations": [
                    serialize_event(
                        row["event"],
                        reason=" · ".join(row["reasons"]),
                        score=row["score"],
                    )
                    for row in recommendations
                ],
                "trending": [serialize_event(row["event"], score=row["score"]) for row in trending],
            }
        )


class BookmarkListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        bookmarks = EventBookmark.objects.filter(user=request.user).select_related(
            "event",
            "event__activity",
            "event__activity__space",
            "event__category",
            "event__venue",
        )[:100]
        return Response(
            [
                {
                    "id": str(bookmark.pk),
                    "created_at": bookmark.created_at,
                    "event": serialize_event(bookmark.event),
                }
                for bookmark in bookmarks
            ]
        )

    def post(self, request):
        event_id = request.data.get("event_id")
        event = get_object_or_404(public_discovery_events(), pk=event_id)
        bookmark, created = EventBookmark.objects.get_or_create(user=request.user, event=event)
        return Response(
            {
                "id": str(bookmark.pk),
                "created": created,
                "event": serialize_event(event),
            },
            status=201 if created else 200,
        )


class BookmarkDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, event_id):
        EventBookmark.objects.filter(user=request.user, event_id=event_id).delete()
        return Response(status=204)
