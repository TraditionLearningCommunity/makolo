from django.urls import path

from .views import BookmarkDetailAPIView, BookmarkListCreateAPIView, DiscoveryEventsAPIView, DiscoveryForYouAPIView


app_name = "discovery_api"

urlpatterns = [
    path("events/", DiscoveryEventsAPIView.as_view(), name="events"),
    path("for-you/", DiscoveryForYouAPIView.as_view(), name="for-you"),
    path("bookmarks/", BookmarkListCreateAPIView.as_view(), name="bookmarks"),
    path("bookmarks/<uuid:event_id>/", BookmarkDetailAPIView.as_view(), name="bookmark-detail"),
]
