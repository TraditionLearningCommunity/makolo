from django.urls import path

from .views import TransportBookView, TransportDepartureDetailView, TransportSearchView


app_name = "transport"

urlpatterns = [
    path("", TransportSearchView.as_view(), name="search"),
    path("departures/<uuid:pk>/", TransportDepartureDetailView.as_view(), name="departure-detail"),
    path(
        "departures/<uuid:departure_id>/book/<uuid:offer_id>/",
        TransportBookView.as_view(),
        name="book",
    ),
]
