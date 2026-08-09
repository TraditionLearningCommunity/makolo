from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/accounts/", include("accounts.api.urls")),
    path("api/v1/organizations/", include("organizations.api.urls")),
    path("api/v1/events/", include("events.api.urls")),
    path("api/v1/tickets/", include("tickets.api.urls")),
    path("api/v1/scanner/", include("scanner.api.urls")),
    path("api/v1/payments/", include("payments.api.urls")),
    path("api/v1/notifications/", include("notifications.api.urls")),
    path("api/v1/analytics/", include("analytics_app.api.urls")),
    path("api/v1/partners/", include("partners.api.urls")),
    path("api/v1/crm/", include("crm.api.urls")),
    path("api/v1/automation/", include("automation.api.urls")),
    path("api/v1/promotions/", include("promotions.api.urls")),
    path("api/v1/loyalty/", include("loyalty.api.urls")),
    path("api/v1/operations/", include("operations.api.urls")),
    path("api/v1/discovery/", include("discovery.api.urls")),
    path("api/v1/growth/", include("growth.api.urls")),
    path("g/", include("growth.public_urls")),
    path("o/", include("organizations.public_urls")),
    path("organizations/", include("organizations.urls")),
    path("autopilot/", include("automation.urls")),
    path("discover/", include("discovery.urls")),
    path("growth/", include("growth.urls")),
    path("events/", include("events.urls")),
    path("tickets/", include("tickets.urls")),
    path("scanner/", include("scanner.urls")),
    path("payments/", include("payments.urls")),
    path("notifications/", include("notifications.urls")),
    path("analytics/", include("analytics_app.urls")),
    path("partners/", include("partners.urls")),
    path("crm/", include("crm.urls")),
    path("promotions/", include("promotions.urls")),
    path("loyalty/", include("loyalty.urls")),
    path("operations/", include("operations.urls")),
    path("", include("core.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
