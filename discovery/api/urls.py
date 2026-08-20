from django.urls import path

from .views import (
    BookmarkDetailAPIView,
    BookmarkListCreateAPIView,
    DiscoveryForYouAPIView,
    DiscoveryItemsAPIView,
    DiscoveryMapAPIView,
)


app_name = "discovery_api"

urlpatterns = [
    path("items/", DiscoveryItemsAPIView.as_view(), name="items"),
    path("map/", DiscoveryMapAPIView.as_view(), name="map"),
    path("for-you/", DiscoveryForYouAPIView.as_view(), name="for-you"),
    path("bookmarks/", BookmarkListCreateAPIView.as_view(), name="bookmarks"),
    path("bookmarks/<uuid:event_id>/", BookmarkDetailAPIView.as_view(), name="bookmark-detail"),
]
