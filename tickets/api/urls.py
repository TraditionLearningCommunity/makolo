from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    TicketOrderViewSet,
    TicketTransferViewSet,
    TicketTypeViewSet,
    TicketViewSet,
    TicketWaitlistViewSet,
)


router = DefaultRouter()
router.register("types", TicketTypeViewSet, basename="ticket-types")
router.register("orders", TicketOrderViewSet, basename="ticket-orders")
router.register("tickets", TicketViewSet, basename="tickets")
router.register("waitlist", TicketWaitlistViewSet, basename="ticket-waitlist")
router.register("transfers", TicketTransferViewSet, basename="ticket-transfers")

urlpatterns = [
    path("", include(router.urls)),
]
