from django.urls import path

from .views import (
    EventCancelView,
    EventCompleteView,
    EventCreateView,
    EventDetailView,
    EventListView,
    EventPublishView,
    EventReopenView,
    EventUpdateView,
)

app_name = "events"

urlpatterns = [
    path("", EventListView.as_view(), name="list"),
    path("new/", EventCreateView.as_view(), name="create"),
    path("<slug:slug>/", EventDetailView.as_view(), name="detail"),
    path("<slug:slug>/edit/", EventUpdateView.as_view(), name="edit"),
    path("<slug:slug>/publish/", EventPublishView.as_view(), name="publish"),
    path("<slug:slug>/cancel/", EventCancelView.as_view(), name="cancel"),
    path("<slug:slug>/complete/", EventCompleteView.as_view(), name="complete"),
    path("<slug:slug>/reopen/", EventReopenView.as_view(), name="reopen"),
]
