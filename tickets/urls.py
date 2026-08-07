from django.urls import path

from .views import (
    EventTicketOrderView,
    MyTicketListView,
    TicketDetailView,
    TicketOrderCancelView,
    TicketOrderDetailView,
    TicketQrView,
    TicketTypeCreateView,
    TicketTypeListView,
    TicketTypeUpdateView,
)


app_name = "tickets"

urlpatterns = [
    path("", MyTicketListView.as_view(), name="list"),
    path("manage/types/", TicketTypeListView.as_view(), name="manage-types"),
    path("manage/types/new/", TicketTypeCreateView.as_view(), name="type-create"),
    path(
        "manage/types/<uuid:pk>/edit/",
        TicketTypeUpdateView.as_view(),
        name="type-edit",
    ),
    path("buy/<slug:event_slug>/", EventTicketOrderView.as_view(), name="order-create"),
    path("orders/<uuid:pk>/", TicketOrderDetailView.as_view(), name="order-detail"),
    path(
        "orders/<uuid:pk>/cancel/",
        TicketOrderCancelView.as_view(),
        name="order-cancel",
    ),
    path("<uuid:pk>/qr.png", TicketQrView.as_view(), name="qr"),
    path("<uuid:pk>/", TicketDetailView.as_view(), name="detail"),
]
