import uuid

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.generic import TemplateView

from activities.models import ActivityStatus, ActivityVisibility
from social.models import ActionNeed, ActionNeedIntakePolicy, ActionNeedStatus, ActionNeedVisibility

from .forms import FundingConfigurationForm, FundingContributionForm
from .models import FundingDetails
from .selectors import funding_accepts_contributions, funding_progress
from .services import can_manage_funding, create_funding, create_funding_contribution, update_funding


def _public_funding(pk):
    return get_object_or_404(
        FundingDetails.objects.select_related("activity", "activity__space", "activity__owner_profile"),
        pk=pk,
        activity__status=ActivityStatus.PUBLISHED,
        activity__visibility=ActivityVisibility.PUBLIC,
    )


def _open_public_needs(activity):
    now = timezone.now()
    return (
        ActionNeed.objects.filter(
            activity=activity,
            status=ActionNeedStatus.OPEN,
            visibility=ActionNeedVisibility.PUBLIC,
            intake_policy=ActionNeedIntakePolicy.OPEN,
        )
        .filter(Q(opens_at__isnull=True) | Q(opens_at__lte=now))
        .filter(Q(closes_at__isnull=True) | Q(closes_at__gt=now))
        .order_by("created_at", "id")
    )


class FundingDetailView(TemplateView):
    template_name = "funding/detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        funding = _public_funding(kwargs["pk"])
        context.update(
            {
                "funding": funding,
                "activity": funding.activity,
                "progress": funding_progress(funding),
                "accepts_contributions": funding_accepts_contributions(funding),
                "contribution_form": FundingContributionForm(funding=funding),
                "client_reference": uuid.uuid4().hex,
                "help_needs": list(_open_public_needs(funding.activity)),
            }
        )
        return context


class FundingCreateView(LoginRequiredMixin, TemplateView):
    template_name = "funding/form.html"
    login_url = "core:login"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form"] = kwargs.get("form") or FundingConfigurationForm(actor=self.request.user)
        context["form_title"] = "Créer un financement"
        return context

    def post(self, request):
        form = FundingConfigurationForm(request.POST, actor=request.user)
        if form.is_valid():
            try:
                funding = create_funding(actor=request.user, **form.cleaned_data)
            except (ValidationError, PermissionDenied) as exc:
                form.add_error(None, "; ".join(getattr(exc, "messages", [str(exc)])))
            else:
                messages.success(request, "Financement créé.")
                if funding.activity.status == ActivityStatus.PUBLISHED and funding.activity.visibility == ActivityVisibility.PUBLIC:
                    return redirect("funding:detail", pk=funding.pk)
                return redirect("funding:manage", pk=funding.pk)
        return self.render_to_response(self.get_context_data(form=form), status=400)


class FundingManageView(LoginRequiredMixin, TemplateView):
    template_name = "funding/form.html"
    login_url = "core:login"

    def _funding(self):
        funding = get_object_or_404(
            FundingDetails.objects.select_related("activity", "activity__space", "activity__owner_profile"),
            pk=self.kwargs["pk"],
        )
        if not can_manage_funding(self.request.user, funding):
            raise PermissionDenied("Vous n’avez pas l’autorité nécessaire pour gérer ce financement.")
        return funding

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        funding = self._funding()
        context["funding"] = funding
        context["form"] = kwargs.get("form") or FundingConfigurationForm(actor=self.request.user, funding=funding)
        context["form_title"] = "Configurer le financement"
        context["progress"] = funding_progress(funding)
        return context

    def post(self, request, pk):
        funding = self._funding()
        form = FundingConfigurationForm(request.POST, actor=request.user, funding=funding)
        if form.is_valid():
            cleaned = dict(form.cleaned_data)
            cleaned.pop("space", None)
            try:
                funding = update_funding(actor=request.user, funding=funding, **cleaned)
            except (ValidationError, PermissionDenied) as exc:
                form.add_error(None, "; ".join(getattr(exc, "messages", [str(exc)])))
            else:
                messages.success(request, "Financement mis à jour.")
                if funding.activity.status == ActivityStatus.PUBLISHED and funding.activity.visibility == ActivityVisibility.PUBLIC:
                    return redirect("funding:detail", pk=funding.pk)
                return redirect("funding:manage", pk=funding.pk)
        return self.render_to_response(self.get_context_data(form=form), status=400)


class FundingContributeView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, pk):
        funding = _public_funding(pk)
        form = FundingContributionForm(request.POST, funding=funding)
        if not form.is_valid():
            messages.error(request, "; ".join(message for errors in form.errors.values() for message in errors))
            return redirect("funding:detail", pk=funding.pk)
        try:
            contribution = create_funding_contribution(
                funding=funding,
                actor=request.user,
                amount=form.cleaned_data["amount"],
                client_reference=request.POST.get("client_reference") or None,
            )
        except (ValidationError, PermissionDenied) as exc:
            messages.error(request, "; ".join(getattr(exc, "messages", [str(exc)])))
            return redirect("funding:detail", pk=funding.pk)
        return redirect("payments:obligation-start", obligation_pk=contribution.payment_obligation_id)
