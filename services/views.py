from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.views.generic import FormView, TemplateView

from activities.models import ActivityStatus, ActivityVisibility
from opportunities.selectors import published_opportunities
from journeys.models import JourneyStatus

from .forms import ServiceIntakeForm, ServiceStartForm
from .models import OpportunityPolicy, ServiceDetails, ServiceIntakeQuestion, ServicePlanTemplateStatus
from .selectors import service_journeys_visible_to
from .services import answer_intake_question, create_service_journey, submit_service_journey


def public_services():
    return ServiceDetails.objects.filter(activity__status=ActivityStatus.PUBLISHED, activity__visibility=ActivityVisibility.PUBLIC).select_related("activity", "activity__space", "activity__owner_profile").order_by("activity__title", "id")


def _published_template(service):
    return service.plan_templates.filter(status=ServicePlanTemplateStatus.PUBLISHED).order_by("-version", "-created_at").first()


def _intake_questions(journey):
    context = journey.service_context
    query = Q(service=context.journey.activity.service_details)
    if context.service_plan_template_id:
        query |= Q(template=context.service_plan_template)
    return ServiceIntakeQuestion.objects.filter(query).order_by("position", "created_at", "id")


class ServiceCatalogView(TemplateView):
    template_name = "services/catalog.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        qs = public_services()
        opportunity = None
        opportunity_id = self.request.GET.get("opportunity")
        if opportunity_id:
            opportunity = published_opportunities().filter(pk=opportunity_id).first()
            if opportunity is not None:
                qs = qs.exclude(opportunity_policy=OpportunityPolicy.NONE)
        context.update({"services": qs, "opportunity": opportunity})
        return context


class ServiceStartView(LoginRequiredMixin, FormView):
    template_name = "services/start.html"
    form_class = ServiceStartForm
    login_url = "core:login"

    def dispatch(self, request, *args, **kwargs):
        self.service = get_object_or_404(public_services(), pk=kwargs["pk"])
        self.initial_opportunity = None
        opportunity_id = request.GET.get("opportunity") or request.POST.get("opportunity")
        if opportunity_id:
            self.initial_opportunity = published_opportunities().filter(pk=opportunity_id).first()
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update({"service": self.service, "initial_opportunity": self.initial_opportunity})
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({"service": self.service, "initial_opportunity": self.initial_opportunity})
        return context

    def form_valid(self, form):
        opportunity = form.cleaned_data.get("opportunity")
        revision = opportunity.current_revision if opportunity is not None else None
        journey = create_service_journey(
            service=self.service,
            initiated_by=self.request.user,
            beneficiary=self.request.user,
            objective=form.cleaned_data.get("objective", ""),
            template=_published_template(self.service),
            opportunity=opportunity,
            opportunity_revision=revision,
        )
        return redirect("services:intake", pk=journey.pk)


class ServiceIntakeView(LoginRequiredMixin, FormView):
    template_name = "services/intake.html"
    form_class = ServiceIntakeForm
    login_url = "core:login"

    def dispatch(self, request, *args, **kwargs):
        self.journey = service_journeys_visible_to(request.user).select_related("activity__service_details", "service_context__service_plan_template", "service_context__opportunity__current_revision").filter(pk=kwargs["pk"], beneficiary=request.user).first()
        if self.journey is None:
            raise Http404
        if self.journey.status != JourneyStatus.DRAFT:
            return redirect("core:participant-journey-detail", pk=self.journey.pk)
        self.questions = list(_intake_questions(self.journey))
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["questions"] = self.questions
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({"journey": self.journey, "questions": self.questions})
        return context

    def form_valid(self, form):
        questions_by_id = {question.pk: question for question in self.questions}
        for question_id, value in form.cleaned_data["intake_values"].items():
            answer_intake_question(journey=self.journey, question=questions_by_id[question_id], value=value, actor=self.request.user)
        if self.request.POST.get("action") == "submit":
            journey = submit_service_journey(journey=self.journey, actor=self.request.user)
            if journey.status == JourneyStatus.CONFIRMED:
                messages.success(self.request, "Votre démarche a été créée et confirmée.")
            else:
                messages.success(self.request, "Votre demande a été envoyée pour revue.")
            return redirect("core:participant-journey-detail", pk=journey.pk)
        messages.success(self.request, "Vos réponses ont été enregistrées.")
        return redirect("services:intake", pk=self.journey.pk)
