from django.urls import path

from .views import (
    OrganizationPromotionsView,
    PromotionCodeCreateView,
    PromotionCodeEditView,
    PromotionCodeToggleView,
    PromotionCreateView,
    PromotionDetailView,
    PromotionEditView,
    PromotionsHomeView,
    PromotionToggleView,
)


app_name = "promotions"

urlpatterns = [
    path("", PromotionsHomeView.as_view(), name="dashboard"),
    path("org/<slug:slug>/", OrganizationPromotionsView.as_view(), name="organization"),
    path("org/<slug:slug>/new/", PromotionCreateView.as_view(), name="create"),
    path("<uuid:pk>/", PromotionDetailView.as_view(), name="detail"),
    path("<uuid:pk>/edit/", PromotionEditView.as_view(), name="edit"),
    path("<uuid:pk>/toggle/", PromotionToggleView.as_view(), name="toggle"),
    path("<uuid:pk>/codes/new/", PromotionCodeCreateView.as_view(), name="code-create"),
    path("codes/<uuid:pk>/edit/", PromotionCodeEditView.as_view(), name="code-edit"),
    path("codes/<uuid:pk>/toggle/", PromotionCodeToggleView.as_view(), name="code-toggle"),
]
