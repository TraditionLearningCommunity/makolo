from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect
from django.views import View
from django.views.generic import TemplateView

from events.selectors import get_public_discoverable_events
from organizations.console_context import authorized_spaces
from organizations.models import Organization, OrganizationVerificationStatus

from .capabilities import get_web_capabilities
from .web_throttling import (
    RATE_LIMIT_MESSAGE,
    allow_web_request,
    client_rate_identity,
    value_rate_identity,
)


class RateLimitedLoginView(LoginView):
    template_name = "auth/login.html"
    redirect_authenticated_user = True

    def post(self, request, *args, **kwargs):
        username = request.POST.get("username", "")
        account_allowed = allow_web_request(
            request,
            scope="login-account",
            limit=10,
            window_seconds=60,
            identities=[value_rate_identity("account", username)],
        )
        ip_allowed = allow_web_request(
            request,
            scope="login-ip",
            limit=60,
            window_seconds=60,
            identities=[client_rate_identity(request)],
        )
        if not account_allowed or not ip_allowed:
            form = self.get_form()
            form.add_error(None, RATE_LIMIT_MESSAGE)
            response = self.form_invalid(form)
            response.status_code = 429
            return response
        return super().post(request, *args, **kwargs)


def _authenticated_landing(user):
    capabilities = get_web_capabilities(user)
    if capabilities["has_organizer_tools"]:
        space = authorized_spaces(user).first()
        if space is not None:
            return "space", space
    if user.is_staff:
        return "operations", None
    return "personal", None


class PublicHomeView(TemplateView):
    template_name = "core/public_home.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            target, space = _authenticated_landing(request.user)
            if target == "space":
                return redirect("organizations:console-entry", slug=space.slug)
            if target == "operations":
                return redirect("operations:dashboard")
            return redirect("core:participant-home")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["featured_events"] = get_public_discoverable_events().order_by("start_at")[:6]
        context["public_organizations"] = (
            Organization.objects.filter(public_profile=True)
            .exclude(verification_status=OrganizationVerificationStatus.SUSPENDED)
            .order_by("name")[:6]
        )
        return context


class DashboardView(LoginRequiredMixin, View):
    """Compatibility URL that now routes to the single professional Space Console."""

    login_url = "core:login"

    def get(self, request, *args, **kwargs):
        target, space = _authenticated_landing(request.user)
        if target == "space":
            return redirect("organizations:console-entry", slug=space.slug)
        if target == "operations":
            return redirect("operations:dashboard")
        return redirect("core:participant-home")
