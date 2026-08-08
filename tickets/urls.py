from django.urls import path

from .views import (
    EventTicketOrderView,
    MyTicketListView,
    TicketDetailView,
    TicketOrderCancelView,
    TicketOrderDetailView,
    TicketQrView,
    TicketTransferAcceptView,
    TicketTransferCancelView,
    TicketTransferCreateView,
    TicketTransferDeclineView,
    TicketTypeCreateView,
    TicketTypeListView,
    TicketTypeUpdateView,
    TransferListView,
    WaitlistAcceptView,
    WaitlistJoinView,
    WaitlistLeaveView,
    WaitlistListView,
)


app_name = "tickets"

urlpatterns = [
    path("", MyTicketListView.as_view(), name="list"),
    path("waitlist/", WaitlistListView.as_view(), name="waitlist-list"),
    path(
        "waitlist/join/<uuid:ticket_type_id>/",
        WaitlistJoinView.as_view(),
        name="waitlist-join",
    ),
    path(
        "waitlist/<uuid:pk>/leave/",
        WaitlistLeaveView.as_view(),
        name="waitlist-leave",
    ),
    path(
        "waitlist/<uuid:pk>/accept/",
        WaitlistAcceptView.as_view(),
        name="waitlist-accept",
    ),
    path("transfers/", TransferListView.as_view(), name="transfer-list"),
    path(
        "transfers/<uuid:pk>/accept/",
        TicketTransferAcceptView.as_view(),
        name="transfer-accept",
    ),
    path(
        "transfers/<uuid:pk>/decline/",
        TicketTransferDeclineView.as_view(),
        name="transfer-decline",
    ),
    path(
        "transfers/<uuid:pk>/cancel/",
        TicketTransferCancelView.as_view(),
        name="transfer-cancel",
    ),
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
    path("<uuid:pk>/transfer/", TicketTransferCreateView.as_view(), name="transfer-create"),
    path("<uuid:pk>/", TicketDetailView.as_view(), name="detail"),
]
