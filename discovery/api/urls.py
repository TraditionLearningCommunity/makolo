from django.urls import path

from .views import (
    BookmarkDetailAPIView,
    BookmarkListCreateAPIView,
    DiscoveryForYouAPIView,
    DiscoveryItemDetailAPIView,
    DiscoveryItemSavedAPIView,
    DiscoveryItemsAPIView,
    DiscoveryMapAPIView,
    DiscoveryWatchDetailAPIView,
    DiscoveryWatchListCreateAPIView,
    DiscoveryWatchResultsAPIView,
)


app_name = "discovery_api"

urlpatterns = [
    path("items/", DiscoveryItemsAPIView.as_view(), name="items"),
    path(
        "items/<str:family>/<uuid:item_id>/",
        DiscoveryItemDetailAPIView.as_view(),
        name="item-detail",
    ),
    path(
        "items/<str:family>/<uuid:item_id>/saved/",
        DiscoveryItemSavedAPIView.as_view(),
        name="item-saved",
    ),
    path("map/", DiscoveryMapAPIView.as_view(), name="map"),
    path("for-you/", DiscoveryForYouAPIView.as_view(), name="for-you"),
    path("bookmarks/", BookmarkListCreateAPIView.as_view(), name="bookmarks"),
    path(
        "bookmarks/<uuid:event_id>/",
        BookmarkDetailAPIView.as_view(),
        name="bookmark-detail",
    ),
    path(
        "watches/",
        DiscoveryWatchListCreateAPIView.as_view(),
        name="watches",
    ),
    path(
        "watches/<uuid:watch_id>/",
        DiscoveryWatchDetailAPIView.as_view(),
        name="watch-detail",
    ),
    path(
        "watches/<uuid:watch_id>/results/",
        DiscoveryWatchResultsAPIView.as_view(),
        name="watch-results",
    ),
]
