from django.contrib import admin
from django.urls import include, path


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/accounts/", include("accounts.api.urls")),
    path("api/v1/events/", include("events.api.urls")),
    path("api/v1/tickets/", include("tickets.api.urls")),
    path("events/", include("events.urls")),
    path("tickets/", include("tickets.urls")),
    path("", include("core.urls")),
]
