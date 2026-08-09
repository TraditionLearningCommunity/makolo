from django.urls import path

from .public_views import MarketingLinkRedirectView


app_name = "growth_public"

urlpatterns = [
    path("<str:code>/", MarketingLinkRedirectView.as_view(), name="redirect"),
]
