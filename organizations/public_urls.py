from django.urls import path

from .views import PublicOrganizationDetailView


app_name = "organizer_public"

urlpatterns = [
    path("<slug:slug>/", PublicOrganizationDetailView.as_view(), name="detail"),
]
