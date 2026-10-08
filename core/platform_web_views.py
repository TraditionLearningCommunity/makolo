"""Web-first operator presentation; all facts and authority belong to owners."""
from datetime import timedelta

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.generic import TemplateView

from authorization.constants import PermissionCode
from authorization.services import can
from core.platform_presentation import platform_modules_for
from operations.product_overview import build_product_operations_overview
from operations.selectors import (
    get_operations_audit_logs, get_operations_incidents,
    get_operations_organizations, get_worker_heartbeats,
)


class PlatformView(LoginRequiredMixin, TemplateView):
    login_url = "core:login"
    template_name = "platform/page.html"
    module = None
    page = "overview"
    heading = "Vue d'ensemble"

    def dispatch(self, request, *args, **kwargs):
        self.platform_modules = platform_modules_for(request.user)
        if not self.platform_modules or (
            self.module and self.module not in {item["key"] for item in self.platform_modules}
        ):
            raise PermissionDenied("Autorité Platform requise.")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            platform_modules=self.platform_modules,
            platform_page=self.page,
            platform_heading=self.heading,
        )
        return context


class PlatformHomeView(PlatformView):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        modules = {row["key"] for row in self.platform_modules}
        if "operations" in modules:
            context["overview"] = build_product_operations_overview(self.request.user)
        else:
            context["limited_operator"] = True
        return context


class PlatformOperationsView(PlatformView):
    module = "operations"
    page = "operations"
    heading = "Opérations"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["overview"] = build_product_operations_overview(self.request.user)
        return context


class PlatformSystemView(PlatformView):
    module = "operations"
    page = "system"
    heading = "État du runtime"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["overview"] = build_product_operations_overview(self.request.user)
        return context


class PlatformAuditView(PlatformView):
    module = "operations"
    page = "audit"
    heading = "Journal opérateur"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["audit_rows"] = get_operations_audit_logs(self.request.user).order_by("-created_at")[:60]
        return context


class PlatformInvestigateView(PlatformView):
    """Conservative, owner-scoped investigation: no global PII or raw model search."""
    module = "operations"
    page = "investigate"
    heading = "Investiguer"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        q = (self.request.GET.get("q") or "").strip()[:100]
        context["query"] = q
        if q:
            context["investigation_spaces"] = get_operations_organizations(self.request.user).filter(
                slug__icontains=q
            )[:20]
            context["investigation_incidents"] = get_operations_incidents(self.request.user).filter(
                title__icontains=q
            ).order_by("-created_at")[:20]
        context["coverage"] = "Operations uniquement : Espaces par identifiant public et incidents par titre."
        return context


class PlatformInteroperabilityView(PlatformView):
    module = "interoperability"
    page = "interoperability"
    heading = "Interopérabilité"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from intelligence.interoperability import (
            platform_provider_connections, project_provider_connection,
        )
        context["connections"] = [
            project_provider_connection(item, manageable=True)
            for item in platform_provider_connections()
        ]
        return context


class PlatformRecognitionView(PlatformView):
    module = "recognition_governance"
    page = "recognition"
    heading = "Gouvernance Recognition"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from recognition.models import RecognitionPolicy
        context["policies"] = RecognitionPolicy.objects.all()[:80]
        context["can_simulate"] = can(
            self.request.user, PermissionCode.PLATFORM_RECOGNITION_POLICY_MANAGE
        )
        context["can_publish"] = can(
            self.request.user, PermissionCode.PLATFORM_RECOGNITION_POLICY_PUBLISH
        )
        return context


class PlatformRecognitionSimulationView(PlatformRecognitionView):
    page = "recognition_simulation"
    heading = "Simulation Recognition"

    def dispatch(self, request, *args, **kwargs):
        if not can(request.user, PermissionCode.PLATFORM_RECOGNITION_POLICY_MANAGE):
            raise PermissionDenied("Permission de simulation Recognition requise.")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from recognition.models import PolicyStatus, RecognitionPolicy
        from recognition.simulation import simulate_policy
        policy = get_object_or_404(
            RecognitionPolicy.objects.filter(
                status__in=(PolicyStatus.DRAFT, PolicyStatus.SIMULATED)
            ), pk=self.kwargs["pk"]
        )
        now = timezone.now()
        context["policy"] = policy
        context["simulation"] = simulate_policy(
            policy=policy, starts_at=now - timedelta(days=30), ends_at=now
        )
        context["simulated_at"] = now
        return context
