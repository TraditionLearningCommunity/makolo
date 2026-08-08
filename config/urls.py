from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/accounts/", include("accounts.api.urls")),
    path("api/v1/events/", include("events.api.urls")),
    path("api/v1/tickets/", include("tickets.api.urls")),
    path("api/v1/scanner/", include("scanner.api.urls")),
    path("api/v1/payments/", include("payments.api.urls")),
    path("api/v1/notifications/", include("notifications.api.urls")),
    path("events/", include("events.urls")),
    path("tickets/", include("tickets.urls")),
    path("scanner/", include("scanner.urls")),
    path("payments/", include("payments.urls")),
    path("notifications/", include("notifications.urls")),
    path("", include("core.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
