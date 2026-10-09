from django.urls import path

from .views import (
    NotificationDetailAPIView,
    NotificationListAPIView,
    NotificationMarkAllReadAPIView,
    NotificationMarkReadAPIView,
    NotificationUnreadCountAPIView,
    NotificationUnreadPresenceAPIView,
    PushEndpointAPIView,
)


urlpatterns = [
    path("", NotificationListAPIView.as_view(), name="notification-list"),
    path("unread-count/", NotificationUnreadCountAPIView.as_view(), name="notification-unread-count"),
    path("unread-presence/", NotificationUnreadPresenceAPIView.as_view(), name="notification-unread-presence"),
    path("read-all/", NotificationMarkAllReadAPIView.as_view(), name="notification-read-all"),
    path("push/endpoints/", PushEndpointAPIView.as_view(), name="push-endpoint"),
    path("<uuid:pk>/", NotificationDetailAPIView.as_view(), name="notification-detail"),
    path("<uuid:pk>/read/", NotificationMarkReadAPIView.as_view(), name="notification-read"),
]
