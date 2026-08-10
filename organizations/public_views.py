from django.views.generic import ListView

from .models import Organization, OrganizationVerificationStatus


class PublicOrganizationListView(ListView):
    model = Organization
    template_name = "organizations/public_list.html"
    context_object_name = "organizations"
    paginate_by = 30

    def get_queryset(self):
        queryset = Organization.objects.filter(public_profile=True).exclude(
            verification_status=OrganizationVerificationStatus.SUSPENDED
        )
        query = (self.request.GET.get("q") or "").strip()
        if query:
            queryset = queryset.filter(name__icontains=query)
        return queryset.order_by("name")
