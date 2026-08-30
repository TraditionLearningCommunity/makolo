from django.db.models import Q
from django.views.generic import TemplateView

from authorization.constants import PermissionCode
from authorization.services import activity_ids_with_permission
from services.attention_selectors import facilitator_attention_journeys, manager_attention_journeys
from services.models import ServiceDetails
from services.selectors import service_journeys_visible_to

from .console_views import SpaceConsoleMixin


SERVICE_CONSOLE_PERMISSIONS = (
    PermissionCode.ACTIVITY_SERVICES_CONFIGURE,
    PermissionCode.ACTIVITY_SERVICES_CASES_VIEW_ALL,
    PermissionCode.ACTIVITY_SERVICES_CASES_VIEW_ASSIGNED,
)


def _service_activity_ids(profile):
    collected = set()
    for code in SERVICE_CONSOLE_PERMISSIONS:
        ids = activity_ids_with_permission(profile, code)
        if ids is None:
            return None
        collected.update(ids)
    return collected


class SpaceConsoleServicesView(SpaceConsoleMixin, TemplateView):
    template_name = "organizations/console/services.html"
    module_key = "services"
    page_title = "Services"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        service_ids = _service_activity_ids(self.request.user)
        services = ServiceDetails.objects.filter(activity__space=self.space).select_related("activity")
        if service_ids is not None:
            services = services.filter(activity_id__in=service_ids)
        q = (self.request.GET.get("q") or "").strip()[:120]
        if q:
            services = services.filter(Q(activity__title__icontains=q) | Q(activity__short_description__icontains=q))

        cases = service_journeys_visible_to(self.request.user).filter(activity__space=self.space).select_related(
            "activity", "beneficiary", "service_context"
        )
        attention_ids = facilitator_attention_journeys(self.request.user).filter(activity__space=self.space).values("pk").union(
            manager_attention_journeys(self.request.user).filter(activity__space=self.space).values("pk")
        )
        context.update(
            {
                "services": services.order_by("activity__title", "id"),
                "case_page_obj": self.paginate(cases.order_by("-updated_at", "id"), per_page=20),
                "attention_count": cases.filter(pk__in=attention_ids).count(),
                "query": q,
            }
        )
        return context
