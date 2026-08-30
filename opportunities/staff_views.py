from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import TemplateView

from authorization.constants import PermissionCode
from authorization.services import can
from services.attention_selectors import opportunity_curator_attention

from .models import (
    Opportunity,
    OpportunityPublicationStatus,
    OpportunitySource,
    OpportunitySubmission,
    OpportunitySubmissionStatus,
)
from .services import (
    archive_opportunity,
    create_opportunity,
    create_opportunity_revision,
    create_opportunity_source,
    decide_opportunity_submission,
    merge_opportunities,
    publish_opportunity_revision,
    record_source_check,
    start_submission_review,
    withdraw_opportunity,
)
from .staff_forms import (
    OpportunityCreateForm,
    OpportunityMergeForm,
    OpportunityRevisionForm,
    OpportunitySourceCheckForm,
    OpportunitySourceForm,
    OpportunitySubmissionDecisionForm,
)


PAGE_SIZE = 25
OPPORTUNITY_PERMISSIONS = {
    PermissionCode.OPPORTUNITIES_MANAGE,
    PermissionCode.OPPORTUNITIES_REVIEW_SUBMISSIONS,
    PermissionCode.OPPORTUNITIES_SOURCES_VERIFY,
    PermissionCode.OPPORTUNITIES_MERGE,
}


def _has_curator_access(actor):
    return getattr(actor, "is_authenticated", False) and any(can(actor, code) for code in OPPORTUNITY_PERMISSIONS)


def _require_curator(actor):
    if not _has_curator_access(actor):
        raise PermissionDenied("Une autorité Opportunity plateforme est requise.")


def _error_message(exc):
    return "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc)


class OpportunityStaffDashboardView(LoginRequiredMixin, TemplateView):
    template_name = "opportunities/staff_dashboard.html"
    login_url = "core:login"

    def dispatch(self, request, *args, **kwargs):
        _require_curator(request.user)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        q = (self.request.GET.get("q") or "").strip()[:120]
        queryset = Opportunity.objects.select_related("current_revision", "merged_into").order_by("-updated_at", "id")
        if q:
            queryset = queryset.filter(
                Q(current_revision__title__icontains=q)
                | Q(current_revision__issuer_name__icontains=q)
                | Q(revisions__title__icontains=q)
                | Q(revisions__issuer_name__icontains=q)
            ).distinct()
        attention = opportunity_curator_attention(self.request.user)
        context.update(
            {
                "page_obj": Paginator(queryset, PAGE_SIZE).get_page(self.request.GET.get("page")),
                "query": q,
                "attention_submissions": attention["submissions"][:10],
                "attention_sources": attention["sources"][:10],
                "withdrawn_with_active_journeys": attention["withdrawn_with_active_journeys"][:10],
                "can_manage": can(self.request.user, PermissionCode.OPPORTUNITIES_MANAGE),
                "can_review_submissions": can(self.request.user, PermissionCode.OPPORTUNITIES_REVIEW_SUBMISSIONS),
                "can_verify_sources": can(self.request.user, PermissionCode.OPPORTUNITIES_SOURCES_VERIFY),
                "can_merge": can(self.request.user, PermissionCode.OPPORTUNITIES_MERGE),
                "create_form": OpportunityCreateForm(),
            }
        )
        return context


class OpportunityStaffCreateView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, *args, **kwargs):
        form = OpportunityCreateForm(request.POST)
        if form.is_valid():
            try:
                opportunity = create_opportunity(actor=request.user, kind=form.cleaned_data["kind"])
            except (ValidationError, PermissionDenied) as exc:
                messages.error(request, _error_message(exc))
            else:
                messages.success(request, "Opportunity créée en brouillon.")
                return redirect("opportunities:staff-detail", pk=opportunity.pk)
        else:
            messages.error(request, "Le type d'Opportunity est invalide.")
        return redirect("opportunities:staff-dashboard")


class OpportunityStaffDetailView(LoginRequiredMixin, TemplateView):
    template_name = "opportunities/staff_detail.html"
    login_url = "core:login"

    def dispatch(self, request, *args, **kwargs):
        _require_curator(request.user)
        self.opportunity = get_object_or_404(
            Opportunity.objects.select_related("current_revision", "merged_into"),
            pk=kwargs["pk"],
        )
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "opportunity": self.opportunity,
                "revisions": self.opportunity.revisions.order_by("version"),
                "sources": self.opportunity.sources.prefetch_related("checks").order_by("-is_primary", "created_at"),
                "revision_form": OpportunityRevisionForm(),
                "source_form": OpportunitySourceForm(),
                "merge_form": OpportunityMergeForm(canonical=self.opportunity),
                "can_manage": can(self.request.user, PermissionCode.OPPORTUNITIES_MANAGE),
                "can_verify_sources": can(self.request.user, PermissionCode.OPPORTUNITIES_SOURCES_VERIFY),
                "can_merge": can(self.request.user, PermissionCode.OPPORTUNITIES_MERGE),
            }
        )
        return context


class OpportunityStaffRevisionCreateView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, *args, **kwargs):
        opportunity = get_object_or_404(Opportunity, pk=kwargs["pk"])
        form = OpportunityRevisionForm(request.POST)
        if form.is_valid():
            try:
                create_opportunity_revision(opportunity=opportunity, actor=request.user, **form.cleaned_data)
            except (ValidationError, PermissionDenied) as exc:
                messages.error(request, _error_message(exc))
            else:
                messages.success(request, "Nouvelle révision brouillon créée.")
        else:
            messages.error(request, "La révision contient des données invalides.")
        return redirect("opportunities:staff-detail", pk=opportunity.pk)


class OpportunityStaffPublishRevisionView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, *args, **kwargs):
        opportunity = get_object_or_404(Opportunity, pk=kwargs["pk"])
        revision = get_object_or_404(opportunity.revisions, pk=kwargs["revision_pk"])
        try:
            publish_opportunity_revision(opportunity=opportunity, revision=revision, actor=request.user)
        except (ValidationError, PermissionDenied) as exc:
            messages.error(request, _error_message(exc))
        else:
            messages.success(request, "Révision publiée.")
        return redirect("opportunities:staff-detail", pk=opportunity.pk)


class OpportunityStaffSourceCreateView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, *args, **kwargs):
        opportunity = get_object_or_404(Opportunity, pk=kwargs["pk"])
        form = OpportunitySourceForm(request.POST)
        if form.is_valid():
            try:
                create_opportunity_source(opportunity=opportunity, actor=request.user, **form.cleaned_data)
            except (ValidationError, PermissionDenied) as exc:
                messages.error(request, _error_message(exc))
            else:
                messages.success(request, "Source ajoutée.")
        else:
            messages.error(request, "La source est invalide.")
        return redirect("opportunities:staff-detail", pk=opportunity.pk)


class OpportunityStaffSourceCheckView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, *args, **kwargs):
        source = get_object_or_404(OpportunitySource.objects.select_related("opportunity"), pk=kwargs["source_pk"])
        form = OpportunitySourceCheckForm(request.POST)
        if form.is_valid():
            try:
                record_source_check(
                    source=source,
                    result=form.cleaned_data["result"],
                    checked_by=request.user,
                    note=form.cleaned_data["note"],
                )
            except (ValidationError, PermissionDenied) as exc:
                messages.error(request, _error_message(exc))
            else:
                messages.success(request, "Contrôle de source enregistré.")
        else:
            messages.error(request, "Le contrôle de source est invalide.")
        return redirect("opportunities:staff-detail", pk=source.opportunity_id)


class OpportunityStaffLifecycleView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, *args, **kwargs):
        opportunity = get_object_or_404(Opportunity, pk=kwargs["pk"])
        action = request.POST.get("action")
        try:
            if action == "withdraw":
                withdraw_opportunity(opportunity=opportunity, actor=request.user)
                success = "Opportunity retirée."
            elif action == "archive":
                archive_opportunity(opportunity=opportunity, actor=request.user)
                success = "Opportunity archivée."
            else:
                raise ValidationError("Action Opportunity inconnue.")
        except (ValidationError, PermissionDenied) as exc:
            messages.error(request, _error_message(exc))
        else:
            messages.success(request, success)
        return redirect("opportunities:staff-detail", pk=opportunity.pk)


class OpportunityStaffMergeView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, *args, **kwargs):
        canonical = get_object_or_404(Opportunity, pk=kwargs["pk"])
        form = OpportunityMergeForm(request.POST, canonical=canonical)
        if form.is_valid():
            try:
                merge_opportunities(canonical=canonical, duplicate=form.cleaned_data["duplicate"], actor=request.user)
            except (ValidationError, PermissionDenied) as exc:
                messages.error(request, _error_message(exc))
            else:
                messages.success(request, "Doublon fusionné vers l'Opportunity canonique.")
        else:
            messages.error(request, "Cible de fusion invalide.")
        return redirect("opportunities:staff-detail", pk=canonical.pk)


class OpportunityStaffSubmissionReviewView(LoginRequiredMixin, TemplateView):
    template_name = "opportunities/staff_submission_review.html"
    login_url = "core:login"

    def dispatch(self, request, *args, **kwargs):
        if not can(request.user, PermissionCode.OPPORTUNITIES_REVIEW_SUBMISSIONS):
            raise PermissionDenied("La revue des propositions Opportunity n'est pas autorisée.")
        self.submission = get_object_or_404(OpportunitySubmission, pk=kwargs["pk"])
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({"submission": self.submission, "decision_form": OpportunitySubmissionDecisionForm()})
        return context

    def post(self, request, *args, **kwargs):
        if self.submission.status == OpportunitySubmissionStatus.PENDING:
            try:
                start_submission_review(submission=self.submission, actor=request.user)
            except (ValidationError, PermissionDenied) as exc:
                messages.error(request, _error_message(exc))
                return redirect("opportunities:staff-submission-review", pk=self.submission.pk)
            self.submission.refresh_from_db()
        form = OpportunitySubmissionDecisionForm(request.POST)
        if form.is_valid():
            try:
                decide_opportunity_submission(
                    submission=self.submission,
                    actor=request.user,
                    decision=form.cleaned_data["decision"],
                    resolved_opportunity=form.cleaned_data["resolved_opportunity"],
                    review_note=form.cleaned_data["review_note"],
                )
            except (ValidationError, PermissionDenied) as exc:
                messages.error(request, _error_message(exc))
            else:
                messages.success(request, "Proposition Opportunity traitée.")
                return redirect("opportunities:staff-dashboard")
        else:
            messages.error(request, "La décision est invalide.")
        return redirect("opportunities:staff-submission-review", pk=self.submission.pk)
