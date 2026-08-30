from django.urls import path

from .views import ServiceCatalogView, ServiceIntakeView, ServiceStartView

app_name = "services"

urlpatterns = [
    path("", ServiceCatalogView.as_view(), name="list"),
    path("<uuid:pk>/start/", ServiceStartView.as_view(), name="start"),
    path("journeys/<uuid:pk>/intake/", ServiceIntakeView.as_view(), name="intake"),
]
