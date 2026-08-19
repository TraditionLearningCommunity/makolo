from django.urls import path

from .views import SpacePlaceCreateView, SpacePlaceDeactivateView, SpacePlaceUpdateView


urlpatterns = [
    path("<slug:slug>/places/new/", SpacePlaceCreateView.as_view(), name="place-create"),
    path("<slug:slug>/places/<uuid:pk>/edit/", SpacePlaceUpdateView.as_view(), name="place-relation-edit"),
    path("<slug:slug>/places/<uuid:pk>/deactivate/", SpacePlaceDeactivateView.as_view(), name="place-relation-deactivate"),
]
