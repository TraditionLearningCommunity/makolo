import secrets

from django.contrib import messages
from django.core.exceptions import ValidationError as DjangoValidationError
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.views.generic import FormView, TemplateView

from groups.selectors import filter_queryset_by_activity_group_eligibility

from activities.models import ActivityStatus, ActivityVisibility
from organizations.models import SpaceLifecycle
from opportunities.selectors import published_opportunities
from journeys.models import JourneyStatus

from .forms import ServiceIntakeForm, ServiceStartForm
from .native_start import (
    ServiceStartIdempotencyConflict,
    replay_native_start_if_exists,
    start_service_journey_idempotently,
)
from .models import OpportunityPolicy, ServiceDetails, ServiceIntakeQuestion, ServicePlanTemplateStatus
from .selectors import service_journeys_visible_to
from .services import answer_intake_question, create_service_journey, submit_service_journey


def public_services():
    """Only owner-published, publicly discoverable Services.

    The Activity's publication alone does not override Space lifecycle,
    public identity, personal Profile privacy or verification suspension. The separate Group gate
    remains the caller's responsibility.
    """
    return (
        ServiceDetails.objects.filter(
            activity__status=ActivityStatus.PUBLISHED,
            activity__visibility=ActivityVisibility.PUBLIC,
        )
        .filter(
            Q(
                activity__space__isnull=False,
                activity__space__public_profile=True,
                activity__space__searchable=True,
                activity__space__lifecycle=SpaceLifecycle.ACTIVE,
            )
            | (
                Q(
                    activity__space__isnull=True,
                    activity__owner_profile__is_active=True,
                )
                & (
                    Q(activity__owner_profile__profile__isnull=True)
                    | Q(
                        activity__owner_profile__profile__public_profile=True,
                        activity__owner_profile__profile__searchable=True,
                    )
                )
            )
        )
        .exclude(activity__space__verification_status="suspended")
        .select_related("activity", "activity__space", "activity__owner_profile")
        .order_by("activity__title", "id")
    )


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

    def _operation_session_key(self):
        return f"services.start.operation:{self.request.user.pk}:{self.service.pk}"

    def _operation_key(self):
        # The hidden key survives a repeated POST. A session fallback also
        # protects older forms and direct posts, without inventing a Journey.
        posted = (self.request.POST.get("operation_key") or "").strip()
        if posted:
            return posted
        session_key = self._operation_session_key()
        # Each rendered GET form is its own intention, including two tabs of
        # the same Service. The session token is a legacy POST fallback only.
        if self.request.method == "GET":
            key = secrets.token_urlsafe(24)
            self.request.session[session_key] = key
            return key
        key = self.request.session.get(session_key)
        if not isinstance(key, str) or not key:
            key = secrets.token_urlsafe(24)
            self.request.session[session_key] = key
        return key

    def dispatch(self, request, *args, **kwargs):
        self.service = get_object_or_404(
            filter_queryset_by_activity_group_eligibility(
                public_services(), request.user,
            ),
            pk=kwargs["pk"],
        )
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
        context.update({
            "service": self.service,
            "initial_opportunity": self.initial_opportunity,
            "operation_key": self._operation_key(),
        })
        return context

    def post(self, request, *args, **kwargs):
        # Replay an already accepted intention before checking today's
        # Opportunity publication. The pinned revision may have been withdrawn
        # between a successful POST and a browser/network retry.
        operation_key = self._operation_key()
        try:
            replay = replay_native_start_if_exists(
                service=self.service,
                actor=request.user,
                operation_key=operation_key,
                objective=request.POST.get("objective", ""),
                opportunity_id=request.POST.get("opportunity") or None,
            )
        except (ServiceStartIdempotencyConflict, DjangoValidationError) as exc:
            form = self.get_form()
            form.add_error(None, (
                "Cette opération a déjà été utilisée pour une autre demande."
                if isinstance(exc, ServiceStartIdempotencyConflict)
                else "; ".join(exc.messages)
            ))
            return self.form_invalid(form)
        if replay is not None:
            journey, _created = replay
            return redirect("services:intake", pk=journey.pk)
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        operation_key = self._operation_key()
        try:
            journey, _created = start_service_journey_idempotently(
                service=self.service,
                actor=self.request.user,
                operation_key=operation_key,
                objective=form.cleaned_data.get("objective", ""),
                opportunity=form.cleaned_data.get("opportunity"),
            )
        except ServiceStartIdempotencyConflict:
            form.add_error(None, "Cette opération a déjà été utilisée pour une autre demande.")
            return self.form_invalid(form)
        except DjangoValidationError as exc:
            form.add_error(None, "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc))
            return self.form_invalid(form)
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
