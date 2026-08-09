from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views import View
from django.views.generic import FormView, TemplateView

from organizations.models import Organization, OrganizationMembership

from .forms import PromotionCodeForm, PromotionForm
from .models import Promotion, PromotionCode, PromotionRedemption
from .permissions import (
    PROMOTION_VIEW_ROLES,
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
        if self.request.user.is_staff:
            organizations = Organization.objects.all().order_by("name")
        else:
            ids = OrganizationMembership.objects.filter(
                user=self.request.user,
                is_active=True,
                role__in=PROMOTION_VIEW_ROLES,
            ).values_list("organization_id", flat=True)
            organizations = Organization.objects.filter(pk__in=ids).order_by("name")
        context["organizations"] = organizations
        context["promotions_count"] = Promotion.objects.filter(organization__in=organizations).count()
        return context


class OrganizationPromotionsView(LoginRequiredMixin, TemplateView):
    template_name = "promotions/organization.html"
    login_url = "core:login"

    def _organization(self):
        organization = get_object_or_404(Organization, slug=self.kwargs["slug"])
        if not user_can_view_promotions(self.request.user, organization):
            raise PermissionDenied("Vous n'avez pas accès aux promotions de cette organisation.")
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
            raise PermissionDenied("Vous ne pouvez pas créer d'offre pour cette organisation.")
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["organization"] = self.organization
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["organization"] = self.organization
        return context

    def form_valid(self, form):
        data = dict(form.cleaned_data)
        create_promotion(actor=self.request.user, organization=self.organization, **data)
        messages.success(self.request, "Offre promotionnelle créée.")
        return redirect("promotions:organization", slug=self.organization.slug)


class PromotionDetailView(LoginRequiredMixin, TemplateView):
    template_name = "promotions/promotion_detail.html"
    login_url = "core:login"

    def _promotion(self):
        promotion = get_object_or_404(
            Promotion.objects.select_related("organization", "event").prefetch_related("codes", "eligible_ticket_types"),
            pk=self.kwargs["pk"],
        )
        if not user_can_view_promotions(self.request.user, promotion.organization):
            raise PermissionDenied("Vous n'avez pas accès à cette offre.")
        return promotion

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        promotion = self._promotion()
        financials = user_can_view_promotion_financials(self.request.user, promotion.organization)
        context.update(
            {
                "promotion": promotion,
                "metrics": promotion_metrics(promotion, include_financials=financials),
                "recent_redemptions": PromotionRedemption.objects.filter(promotion=promotion).select_related("code", "order")[:50],
                "can_manage": user_can_manage_promotions(self.request.user, promotion.organization),
                "can_view_financials": financials,
                "code_form": PromotionCodeForm(promotion=promotion),
            }
        )
        return context


class PromotionCodeCreateView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, pk):
        promotion = get_object_or_404(Promotion.objects.select_related("organization"), pk=pk)
        if not user_can_manage_promotions(request.user, promotion.organization):
            raise PermissionDenied("Vous ne pouvez pas créer de code pour cette offre.")
        form = PromotionCodeForm(request.POST, promotion=promotion)
        if form.is_valid():
            create_promotion_code(actor=request.user, promotion=promotion, **form.cleaned_data)
            messages.success(request, "Code promotionnel créé.")
        else:
            messages.error(request, "; ".join(message for errors in form.errors.values() for message in errors))
        return redirect("promotions:detail", pk=promotion.pk)


class PromotionToggleView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, pk):
        promotion = get_object_or_404(Promotion.objects.select_related("organization"), pk=pk)
        try:
            promotion = toggle_promotion(actor=request.user, promotion=promotion)
        except (PermissionDenied, ValidationError) as exc:
            messages.error(request, "; ".join(getattr(exc, "messages", [str(exc)])))
        else:
            messages.success(request, "Offre activée." if promotion.is_active else "Offre mise en pause.")
        return redirect("promotions:detail", pk=promotion.pk)


class PromotionCodeToggleView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, pk):
        code = get_object_or_404(
            PromotionCode.objects.select_related("promotion", "promotion__organization"),
            pk=pk,
        )
        try:
            code = toggle_promotion_code(actor=request.user, code=code)
        except (PermissionDenied, ValidationError) as exc:
            messages.error(request, "; ".join(getattr(exc, "messages", [str(exc)])))
        else:
            messages.success(request, "Code activé." if code.is_active else "Code désactivé.")
        return redirect("promotions:detail", pk=code.promotion_id)
