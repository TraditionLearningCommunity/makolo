from django.shortcuts import get_object_or_404
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from discovery.models import EventBookmark
from discovery.services import build_recommendations, build_trending, public_discovery_events, search_discovery_events, serialize_event


class DiscoveryEventsAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        events = search_discovery_events(request.query_params)[:50]
        return Response([serialize_event(event) for event in events])


class DiscoveryForYouAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        recommendations = build_recommendations(request.user, limit=24)
        trending = build_trending(limit=12)
        return Response(
            {
                "recommendations": [
                    serialize_event(row["event"], reason=" · ".join(row["reasons"]), score=row["score"])
                    for row in recommendations
                ],
                "trending": [serialize_event(row["event"], score=row["score"]) for row in trending],
            }
        )


class BookmarkListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        bookmarks = EventBookmark.objects.filter(user=request.user).select_related(
            "event", "event__organization", "event__category", "event__venue"
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
