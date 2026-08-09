from django.urls import path

from .views import BookmarkListView, BookmarkToggleView, DiscoveryHomeView, ForYouView, MyEventsView


app_name = "discovery"

urlpatterns = [
    path("", DiscoveryHomeView.as_view(), name="home"),
    path("for-you/", ForYouView.as_view(), name="for-you"),
    path("bookmarks/", BookmarkListView.as_view(), name="bookmarks"),
    path("bookmarks/<uuid:event_id>/toggle/", BookmarkToggleView.as_view(), name="bookmark-toggle"),
    path("my-events/", MyEventsView.as_view(), name="my-events"),
]
