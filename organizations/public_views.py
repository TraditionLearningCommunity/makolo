from django.views.generic import ListView

from .models import Organization, SpaceLifecycle


class PublicOrganizationListView(ListView):
    model = Organization
    template_name = "organizations/public_list.html"
    context_object_name = "organizations"
    paginate_by = 30

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["surface_base_template"] = "base/app.html" if self.request.user.is_authenticated else "base/public.html"
        return context

    def get_queryset(self):
        queryset = Organization.objects.filter(
            public_profile=True,
            lifecycle=SpaceLifecycle.ACTIVE,
        )
        query = (self.request.GET.get("q") or "").strip()
        if query:
            queryset = queryset.filter(name__icontains=query)
        return queryset.order_by("name")
