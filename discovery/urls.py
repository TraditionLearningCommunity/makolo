from django.urls import path

from .views import (
    BookmarkListView,
    BookmarkToggleView,
    DiscoveryActivityDetailView,
    DiscoveryHomeView,
    ForYouView,
    MyEventsView,
)
from .watch_views import (
    WatchCreateView,
    WatchDeleteView,
    WatchDetailView,
    WatchEditView,
    WatchListView,
    WatchStatusView,
)

app_name = "discovery"

urlpatterns = [
    path("", DiscoveryHomeView.as_view(), name="home"),
    path("activities/<uuid:occurrence_id>/", DiscoveryActivityDetailView.as_view(), name="activity-detail"),
    path("for-you/", ForYouView.as_view(), name="for-you"),
    path("watches/", WatchListView.as_view(), name="watch-list"),
    path("watches/new/", WatchCreateView.as_view(), name="watch-create"),
    path("watches/<uuid:watch_id>/", WatchDetailView.as_view(), name="watch-detail"),
    path("watches/<uuid:watch_id>/edit/", WatchEditView.as_view(), name="watch-edit"),
    path("watches/<uuid:watch_id>/status/", WatchStatusView.as_view(), name="watch-status"),
    path("watches/<uuid:watch_id>/delete/", WatchDeleteView.as_view(), name="watch-delete"),
    path("bookmarks/", BookmarkListView.as_view(), name="bookmarks"),
    path("bookmarks/activities/<uuid:activity_id>/toggle/", BookmarkToggleView.as_view(), name="activity-bookmark-toggle"),
    path("bookmarks/<uuid:event_id>/toggle/", BookmarkToggleView.as_view(), name="bookmark-toggle"),
    path("my-events/", MyEventsView.as_view(), name="my-events"),
]
