from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from core.api.views import HealthAPIView, ReadinessAPIView


handler403 = "core.error_views.error_403"
handler404 = "core.error_views.error_404"
handler500 = "core.error_views.error_500"


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/health/", HealthAPIView.as_view(), name="api-health"),
    path("api/v1/readiness/", ReadinessAPIView.as_view(), name="api-readiness"),
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
    path("account/", include("accounts.web_urls")),
    path("activities/", include("activities.urls")),
    path("spaces/", include("organizations.urls")),
    path("groups/", include("groups.urls")),
    path("autopilot/", include("automation.urls")),
    path("discover/", include("discovery.urls")),
    path("opportunities/", include("opportunities.urls")),
    path("services/", include("services.urls")),
    path("growth/", include("growth.urls")),
    path("transport/", include("transport.urls")),
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
    path("journeys/", include("journeys.urls")),
    path("", include("core.urls")),
]

if getattr(settings, "IS_E2E", False):
    from core.e2e_views import synthetic_server_error

    urlpatterns.append(path("__e2e__/error/500/", synthetic_server_error, name="e2e-error-500"))

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
