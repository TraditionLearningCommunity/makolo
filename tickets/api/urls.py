from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import TicketOrderViewSet, TicketTypeViewSet, TicketViewSet


router = DefaultRouter()
router.register("types", TicketTypeViewSet, basename="ticket-types")
router.register("orders", TicketOrderViewSet, basename="ticket-orders")
router.register("tickets", TicketViewSet, basename="tickets")

urlpatterns = [
    path("", include(router.urls)),
]
