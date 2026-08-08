from django.urls import path

from .views import (
    NotificationListView,
    NotificationMarkAllReadView,
    NotificationMarkReadView,
    NotificationOpenView,
    NotificationPreferenceView,
)


app_name = "notifications"

urlpatterns = [
    path("", NotificationListView.as_view(), name="list"),
    path("preferences/", NotificationPreferenceView.as_view(), name="preferences"),
    path("read-all/", NotificationMarkAllReadView.as_view(), name="read-all"),
    path("<uuid:pk>/open/", NotificationOpenView.as_view(), name="open"),
    path("<uuid:pk>/read/", NotificationMarkReadView.as_view(), name="mark-read"),
]
