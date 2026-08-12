from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import FormView, TemplateView

from authorization.constants import PermissionCode
from authorization.services import space_ids_with_permission
from organizations.models import Organization

from .forms import PromotionCodeForm, PromotionForm
from .models import Promotion, PromotionCode, PromotionRedemption
from .permissions import (
    user_can_manage_promotions,
    user_can_view_promotion_financials,
    user_can_view_promotions,
)
from .services import create_promotion, create_promotion_code, promotion_metrics, toggle_promotion, toggle_promotion_code


class PromotionsHomeView(LoginRequiredMixin, TemplateView):
    template_name = "promotions/dashboard.html"
    login_url = "core:login"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        ids = space_ids_with_permission(self.request.user, PermissionCode.PROMOTIONS_VIEW)
        organizations = Organization.objects.all().order_by("name")
        if ids is not None:
            organizations = organizations.filter(pk__in=ids)
        context["organizations"] = organizations
        context["promotions_count"] = Promotion.objects.filter(organization__in=organizations).count()
        return context


class OrganizationPromotionsView(LoginRequiredMixin, TemplateView):
    template_name = "promotions/organization.html"
    login_url = "core:login"

    def _organization(self):
        organization = get_object_or_404(Organization, slug=self.kwargs["slug"])
        if not user_can_view_promotions(self.request.user, organization):
            raise PermissionDenied("Vous n'avez pas accès aux promotions de cet Espace.")
        return organization

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        organization = self._organization()
        promotions = Promotion.objects.filter(organization=organization).select_related("event").prefetch_related("codes")
        context.update(
            {
                "organization": organization,
                "promotions": promotions,
                "can_manage": user_can_manage_promotions(self.request.user, organization),
                "can_view_financials": user_can_view_promotion_financials(self.request.user, organization),
            }
        )
        return context


class PromotionCreateView(LoginRequiredMixin, FormView):
    template_name = "promotions/promotion_form.html"
    form_class = PromotionForm
    login_url = "core:login"

    def dispatch(self, request, *args, **kwargs):
        self.organization = get_object_or_404(Organization, slug=kwargs["slug"])
        if not user_can_manage_promotions(request.user, self.organization):
            raise PermissionDenied("Vous ne pouvez pas créer d'offre pour cet Espace.")
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["organization"] = self.organization
        return kwargs

    def form_valid(self, form):
        try:
            promotion = create_promotion(
                organization=self.organization,
                actor=self.request.user,
                **form.cleaned_data,
            )
        except ValidationError as exc:
            form.add_error(None, exc)
            return self.form_invalid(form)
        messages.success(self.request, "Offre créée.")
        return redirect("promotions:organization", slug=self.organization.slug)


class PromotionCodeCreateView(LoginRequiredMixin, FormView):
    template_name = "promotions/code_form.html"
    form_class = PromotionCodeForm
    login_url = "core:login"

    def dispatch(self, request, *args, **kwargs):
        self.promotion = get_object_or_404(Promotion.objects.select_related("organization", "event"), pk=kwargs["pk"])
        if not user_can_manage_promotions(request.user, self.promotion.organization):
            raise PermissionDenied("Vous ne pouvez pas gérer les codes de cet Espace.")
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["promotion"] = self.promotion
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["promotion"] = self.promotion
        return context

    def form_valid(self, form):
        try:
            create_promotion_code(
                promotion=self.promotion,
                actor=self.request.user,
                **form.cleaned_data,
            )
        except ValidationError as exc:
            form.add_error(None, exc)
            return self.form_invalid(form)
        messages.success(self.request, "Code promotionnel créé.")
        return redirect("promotions:organization", slug=self.promotion.organization.slug)


class PromotionToggleView(LoginRequiredMixin, View):
    def post(self, request, pk):
        promotion = get_object_or_404(Promotion.objects.select_related("organization"), pk=pk)
        toggle_promotion(promotion=promotion, actor=request.user)
        messages.success(request, "État de l'offre mis à jour.")
        return redirect("promotions:organization", slug=promotion.organization.slug)


class PromotionCodeToggleView(LoginRequiredMixin, View):
    def post(self, request, pk):
        code = get_object_or_404(PromotionCode.objects.select_related("promotion__organization"), pk=pk)
        toggle_promotion_code(code=code, actor=request.user)
        messages.success(request, "État du code mis à jour.")
        return redirect("promotions:organization", slug=code.promotion.organization.slug)


class PromotionMetricsView(LoginRequiredMixin, TemplateView):
    template_name = "promotions/metrics.html"
    login_url = "core:login"

    def dispatch(self, request, *args, **kwargs):
        self.promotion = get_object_or_404(Promotion.objects.select_related("organization", "event"), pk=kwargs["pk"])
        if not user_can_view_promotions(request.user, self.promotion.organization):
            raise PermissionDenied("Vous n'avez pas accès aux statistiques de cette offre.")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        financials = user_can_view_promotion_financials(self.request.user, self.promotion.organization)
        context.update(
            {
                "promotion": self.promotion,
                "metrics": promotion_metrics(self.promotion, include_financials=financials),
                "can_view_financials": financials,
                "redemptions": (
                    PromotionRedemption.objects.filter(promotion=self.promotion)
                    .select_related("order", "code", "buyer")[:100]
                    if financials
                    else []
                ),
            }
        )
        return context
