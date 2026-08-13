from django.urls import path

from .views import SpacePlaceCreateView, SpacePlaceDeactivateView, SpacePlaceListView, SpacePlaceUpdateView

app_name = "geography"

urlpatterns = [
    path("<slug:slug>/places/", SpacePlaceListView.as_view(), name="space-places"),
    path("<slug:slug>/places/new/", SpacePlaceCreateView.as_view(), name="space-place-create"),
    path("<slug:slug>/places/<uuid:pk>/edit/", SpacePlaceUpdateView.as_view(), name="space-place-edit"),
    path("<slug:slug>/places/<uuid:pk>/deactivate/", SpacePlaceDeactivateView.as_view(), name="space-place-deactivate"),
]
