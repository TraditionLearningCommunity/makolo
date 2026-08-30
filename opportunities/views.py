from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.generic import FormView, TemplateView

from .forms import OpportunitySubmissionForm
from .models import OpportunityKind, OpportunitySave
from .selectors import published_opportunities, saved_opportunities, submission_for_owner
from .services import save_opportunity, submit_opportunity, unsave_opportunity

PAGE_SIZE = 24


def _filtered_opportunities(request):
    qs = published_opportunities().prefetch_related("current_revision__zones__zone", "current_revision__requirements", "sources")
    q = (request.GET.get("q") or "").strip()[:120]
    kind = (request.GET.get("kind") or "").strip()
    state = (request.GET.get("state") or "").strip()
    remote = (request.GET.get("remote") or "").strip()
    now = timezone.now()
    if q:
        qs = qs.filter(Q(current_revision__title__icontains=q) | Q(current_revision__issuer_name__icontains=q) | Q(current_revision__summary__icontains=q))
    if kind in OpportunityKind.values:
        qs = qs.filter(kind=kind)
    else:
        kind = ""
    if state == "upcoming":
        qs = qs.filter(current_revision__opens_at__gt=now)
    elif state == "closed":
        qs = qs.filter(current_revision__deadline_at__lte=now)
    elif state == "open":
        qs = qs.filter(Q(current_revision__opens_at__isnull=True) | Q(current_revision__opens_at__lte=now)).filter(Q(current_revision__deadline_at__isnull=True) | Q(current_revision__deadline_at__gt=now))
    else:
        state = ""
    if remote == "yes":
        qs = qs.filter(current_revision__remote_allowed=True)
    elif remote == "no":
        qs = qs.filter(current_revision__remote_allowed=False)
    else:
        remote = ""
    return qs.distinct(), {"q": q, "kind": kind, "state": state, "remote": remote}


class OpportunityListView(TemplateView):
    template_name = "opportunities/list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        qs, filters = _filtered_opportunities(self.request)
        page_obj = Paginator(qs, PAGE_SIZE).get_page(self.request.GET.get("page"))
        saved_ids = set()
        if self.request.user.is_authenticated:
            saved_ids = set(OpportunitySave.objects.filter(profile=self.request.user, opportunity_id__in=[row.pk for row in page_obj.object_list]).values_list("opportunity_id", flat=True))
        query = self.request.GET.copy()
        query.pop("page", None)
        context.update({"page_obj": page_obj, "opportunities": page_obj.object_list, "filters": filters, "kind_choices": OpportunityKind.choices, "saved_ids": saved_ids, "pagination_query": query.urlencode()})
        return context


class OpportunityDetailView(TemplateView):
    template_name = "opportunities/detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        opportunity = get_object_or_404(published_opportunities().prefetch_related("current_revision__zones__zone", "current_revision__requirements", "sources"), pk=kwargs["pk"])
        revision = opportunity.current_revision
        primary_source = next((source for source in opportunity.sources.all() if source.is_primary and source.status == "active"), None)
        is_saved = self.request.user.is_authenticated and OpportunitySave.objects.filter(profile=self.request.user, opportunity=opportunity).exists()
        context.update({"opportunity": opportunity, "revision": revision, "primary_source": primary_source, "is_saved": is_saved, "temporal_state": revision.temporal_state()})
        return context


class OpportunitySaveToggleView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, pk):
        opportunity = get_object_or_404(published_opportunities(), pk=pk)
        if OpportunitySave.objects.filter(profile=request.user, opportunity=opportunity).exists():
            unsave_opportunity(profile=request.user, opportunity=opportunity)
            messages.success(request, "Opportunity retirée de vos favoris.")
        else:
            save_opportunity(profile=request.user, opportunity=opportunity)
            messages.success(request, "Opportunity sauvegardée.")
        next_url = request.POST.get("next")
        return redirect(next_url or reverse("opportunities:detail", kwargs={"pk": opportunity.pk}))


class OpportunitySavedListView(LoginRequiredMixin, TemplateView):
    template_name = "opportunities/saved.html"
    login_url = "core:login"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        page_obj = Paginator(saved_opportunities(self.request.user), PAGE_SIZE).get_page(self.request.GET.get("page"))
        context.update({"page_obj": page_obj, "opportunities": page_obj.object_list})
        return context


class OpportunitySubmissionCreateView(LoginRequiredMixin, FormView):
    template_name = "opportunities/submit.html"
    form_class = OpportunitySubmissionForm
    login_url = "core:login"

    def form_valid(self, form):
        submission = submit_opportunity(submitted_by=self.request.user, **form.cleaned_data)
        messages.success(self.request, "Votre proposition a été envoyée pour revue. Elle n’est pas publiée automatiquement.")
        return redirect("opportunities:submission-detail", pk=submission.pk)


class OpportunitySubmissionDetailView(LoginRequiredMixin, TemplateView):
    template_name = "opportunities/submission_detail.html"
    login_url = "core:login"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        submission = submission_for_owner(submission_id=kwargs["pk"], profile=self.request.user)
        if submission is None:
            raise Http404
        context["submission"] = submission
        return context
