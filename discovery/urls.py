from django.urls import path

from .views import (
    BookmarkListView,
    BookmarkToggleView,
    DiscoveryActivityDetailView,
    DiscoveryHomeView,
    ForYouView,
    MyEventsView,
)


app_name = "discovery"

urlpatterns = [
    path("", DiscoveryHomeView.as_view(), name="home"),
    path("activities/<uuid:occurrence_id>/", DiscoveryActivityDetailView.as_view(), name="activity-detail"),
    path("for-you/", ForYouView.as_view(), name="for-you"),
    path("bookmarks/", BookmarkListView.as_view(), name="bookmarks"),
    path(
        "bookmarks/activities/<uuid:activity_id>/toggle/",
        BookmarkToggleView.as_view(),
        name="activity-bookmark-toggle",
    ),
    # Legacy Event-shaped URL kept for old links/mobile clients; writes still
    # resolve to the canonical Activity bookmark.
    path("bookmarks/<uuid:event_id>/toggle/", BookmarkToggleView.as_view(), name="bookmark-toggle"),
    path("my-events/", MyEventsView.as_view(), name="my-events"),
]
