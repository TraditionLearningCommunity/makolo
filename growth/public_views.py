from django.shortcuts import get_object_or_404, redirect
from django.views import View

from events.models import EventStatus, EventVisibility
from organizations.models import OrganizationVerificationStatus

from .models import MarketingLink
from .services import capture_marketing_link


class MarketingLinkRedirectView(View):
    def get(self, request, code):
        link = get_object_or_404(
            MarketingLink.objects.select_related("event", "organization"),
            code=code,
            is_active=True,
            event__status=EventStatus.PUBLISHED,
            event__visibility=EventVisibility.PUBLIC,
        )
        if link.organization.verification_status == OrganizationVerificationStatus.SUSPENDED:
            from django.http import Http404

            raise Http404
        capture_marketing_link(request, link)
        return redirect("events:detail", slug=link.event.slug)
