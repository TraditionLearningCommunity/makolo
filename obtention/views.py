from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import TemplateView

from activities.models import ActivityStatus, ActivityVisibility
from activities.services import create_occurrence
from authorization.constants import PermissionCode
from authorization.services import activity_ids_with_permission, can
from journeys.models import Journey, JourneyAssignmentStatus, JourneyStep
from journeys.collaboration_services import (
    complete_participant_step,
    complete_step,
    start_participant_step,
    start_step,
)
from readiness import resolve_journey_readiness
from requirements.contracts import RequirementAssessmentState
from requirements.domain_services import assess_journey_requirement

from .forms import ObtentionConfigurationForm, ObtentionOccurrenceForm, ReceiptForm
from .models import ObtentionDetails, ObtentionTarget
from .selectors import (
    fulfillment_for_journey,
    obtention_journey_queryset,
    public_obtentions,
    published_configuration,
)
from .services import (
    activate_obtention_journey,
    create_obtention,
    create_obtention_journey,
    fulfill_obtention_journey,
    record_beneficiary_receipt,
    record_operator_receipt,
    revise_obtention,
)


def _message(exc):
    if hasattr(exc, "message_dict"):
        return "; ".join(
            f"{field}: {', '.join(messages_)}"
            for field, messages_ in exc.message_dict.items()
        )
    return "; ".join(getattr(exc, "messages", [str(exc)]))


def _managed_obtention(actor, pk):
    obtention = get_object_or_404(
        ObtentionDetails.objects.select_related(
            "activity", "activity__space", "activity__owner_profile"
        ),
        pk=pk,
    )
    if not can(actor, PermissionCode.ACTIVITY_MANAGE, activity=obtention.activity):
        raise PermissionDenied("Vous ne pouvez pas gérer cette Obtention.")
    return obtention


def _visible_journey(actor, pk):
    queryset = obtention_journey_queryset()
    allowed = activity_ids_with_permission(actor, PermissionCode.ACTIVITY_MANAGE)
    if allowed is None:
        return get_object_or_404(queryset, pk=pk)
    permission_q = Q(activity_id__in=allowed) if allowed else Q(pk__isnull=True)
    return get_object_or_404(
        queryset.filter(Q(beneficiary=actor) | permission_q).distinct(),
        pk=pk,
    )


class ObtentionDetailView(TemplateView):
    template_name = "obtention/detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        obtention = get_object_or_404(public_obtentions(), pk=kwargs["pk"])
        configuration = (
            obtention.published_configurations[0]
            if getattr(obtention, "published_configurations", None)
            else published_configuration(obtention)
        )
        context.update(
            {
                "obtention": obtention,
                "activity": obtention.activity,
                "configuration": configuration,
                "targets": list(configuration.targets.all()),
                "modes": list(configuration.modes.all()),
            }
        )
        return context


class ObtentionCreateView(LoginRequiredMixin, TemplateView):
    template_name = "obtention/form.html"
    login_url = "core:login"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form"] = kwargs.get("form") or ObtentionConfigurationForm(
            actor=self.request.user
        )
        context["form_title"] = "Créer une Obtention"
        return context

    def post(self, request):
        form = ObtentionConfigurationForm(request.POST, actor=request.user)
        if form.is_valid():
            data = dict(form.cleaned_data)
            space = data.pop("space", None)
            try:
                obtention = create_obtention(actor=request.user, space=space, **data)
            except (PermissionDenied, ValidationError) as exc:
                form.add_error(None, _message(exc))
            else:
                messages.success(request, "Obtention créée.")
                if (
                    obtention.activity.status == ActivityStatus.PUBLISHED
                    and obtention.activity.visibility
                    in {ActivityVisibility.PUBLIC, ActivityVisibility.UNLISTED}
                ):
                    return redirect("obtention:detail", pk=obtention.pk)
                return redirect("obtention:manage", pk=obtention.pk)
        return self.render_to_response(self.get_context_data(form=form), status=400)


class ObtentionManageView(LoginRequiredMixin, TemplateView):
    template_name = "obtention/form.html"
    login_url = "core:login"

    def _obtention(self):
        return _managed_obtention(self.request.user, self.kwargs["pk"])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        obtention = self._obtention()
        context.update(
            {
                "obtention": obtention,
                "activity": obtention.activity,
                "configuration": published_configuration(obtention),
                "occurrences": obtention.activity.occurrences.order_by(
                    "start_date", "start_time", "id"
                ),
                "form": kwargs.get("form")
                or ObtentionConfigurationForm(
                    actor=self.request.user,
                    obtention=obtention,
                ),
                "form_title": "Configurer l’Obtention",
            }
        )
        return context

    def post(self, request, pk):
        obtention = self._obtention()
        form = ObtentionConfigurationForm(
            request.POST,
            actor=request.user,
            obtention=obtention,
        )
        if form.is_valid():
            data = dict(form.cleaned_data)
            data.pop("space", None)
            try:
                revise_obtention(
                    obtention=obtention,
                    actor=request.user,
                    **data,
                )
            except (PermissionDenied, ValidationError) as exc:
                form.add_error(None, _message(exc))
            else:
                messages.success(request, "Obtention mise à jour.")
                return redirect("obtention:manage", pk=obtention.pk)
        return self.render_to_response(self.get_context_data(form=form), status=400)


class ObtentionStartView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, pk):
        obtention = get_object_or_404(public_obtentions(), pk=pk)
        mode = (request.POST.get("mode") or "").strip()
        try:
            journey = create_obtention_journey(
                obtention=obtention,
                actor=request.user,
                mode=mode,
            )
            journey = activate_obtention_journey(
                journey=journey,
                actor=request.user,
            )
        except (PermissionDenied, ValidationError) as exc:
            messages.error(request, _message(exc))
            return redirect("obtention:detail", pk=obtention.pk)
        return redirect("obtention:journey", pk=journey.pk)


class ObtentionJourneyView(LoginRequiredMixin, TemplateView):
    template_name = "obtention/journey.html"
    login_url = "core:login"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        journey = _visible_journey(self.request.user, kwargs["pk"])
        fulfillment = fulfillment_for_journey(journey)
        steps = list(
            journey.steps.prefetch_related("assignments").order_by("position", "created_at", "id")
        )
        has_case_assignment = journey.assignments.filter(
            profile=self.request.user,
            status=JourneyAssignmentStatus.ACTIVE,
        ).exists()
        step_rows = [
            {
                "step": step,
                "can_act": (
                    (
                        journey.beneficiary_id == self.request.user.pk
                        and (
                            step.created_by_id == self.request.user.pk
                            or step.assignments.filter(
                                profile=self.request.user,
                                status=JourneyAssignmentStatus.ACTIVE,
                            ).exists()
                        )
                    )
                    or (
                        has_case_assignment
                        and can(
                            self.request.user,
                            PermissionCode.ACTIVITY_MANAGE,
                            activity=journey.activity,
                        )
                    )
                ),
            }
            for step in steps
        ]
        context.update(
            {
                "journey": journey,
                "obtention": journey.activity.obtention_details,
                "configuration": journey.obtention_context.configuration,
                "mode": journey.obtention_context.mode,
                "fulfillment": fulfillment,
                "readiness": resolve_journey_readiness(
                    journey,
                    viewer=self.request.user
                    if journey.beneficiary_id == self.request.user.pk
                    else None,
                ),
                "is_beneficiary": journey.beneficiary_id == self.request.user.pk,
                "step_rows": step_rows,
                "requirement_assessments": list(
                    journey.requirement_assessments.select_related(
                        "requirement", "journey_step"
                    ).all()
                ),
                "can_manage": can(
                    self.request.user,
                    PermissionCode.ACTIVITY_MANAGE,
                    activity=journey.activity,
                ),
            }
        )
        return context


class ObtentionReceiptView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, pk, target_id):
        journey = _visible_journey(request.user, pk)
        target = get_object_or_404(
            ObtentionTarget,
            pk=target_id,
            configuration=journey.obtention_context.configuration,
        )
        form = ReceiptForm(request.POST)
        if not form.is_valid():
            messages.error(
                request,
                "; ".join(
                    message
                    for errors in form.errors.values()
                    for message in errors
                ),
            )
            return redirect("obtention:journey", pk=journey.pk)
        try:
            record_beneficiary_receipt(
                journey=journey,
                target=target,
                actor=request.user,
                received_quantity=form.cleaned_data["received_quantity"],
            )
        except (PermissionDenied, ValidationError) as exc:
            messages.error(request, _message(exc))
        else:
            messages.success(request, "Réception enregistrée.")
        return redirect("obtention:journey", pk=journey.pk)


class ObtentionOperatorReceiptView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, pk, target_id):
        journey = _visible_journey(request.user, pk)
        target = get_object_or_404(
            ObtentionTarget,
            pk=target_id,
            configuration=journey.obtention_context.configuration,
        )
        quantity = request.POST.get("received_quantity")
        try:
            record_operator_receipt(
                journey=journey,
                target=target,
                actor=request.user,
                received_quantity=quantity if quantity not in {None, ""} else None,
            )
        except (PermissionDenied, ValidationError) as exc:
            messages.error(request, _message(exc))
        else:
            messages.success(request, "Validation du porteur enregistrée.")
        return redirect("obtention:journey", pk=journey.pk)


class ObtentionFulfillView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, pk):
        journey = _visible_journey(request.user, pk)
        try:
            fulfill_obtention_journey(journey=journey, actor=request.user)
        except (PermissionDenied, ValidationError) as exc:
            messages.error(request, _message(exc))
        else:
            messages.success(request, "Obtention accomplie.")
        return redirect("obtention:journey", pk=journey.pk)


class ObtentionStepStartView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, pk, step_id):
        journey = _visible_journey(request.user, pk)
        step = get_object_or_404(JourneyStep, pk=step_id, journey=journey)
        try:
            if journey.beneficiary_id == request.user.pk:
                start_participant_step(step=step, actor=request.user)
            else:
                start_step(step=step, actor=request.user)
        except (PermissionDenied, ValidationError) as exc:
            messages.error(request, _message(exc))
        return redirect("obtention:journey", pk=journey.pk)


class ObtentionStepCompleteView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, pk, step_id):
        journey = _visible_journey(request.user, pk)
        step = get_object_or_404(JourneyStep, pk=step_id, journey=journey)
        try:
            if journey.beneficiary_id == request.user.pk:
                complete_participant_step(step=step, actor=request.user)
            else:
                complete_step(step=step, actor=request.user)
        except (PermissionDenied, ValidationError) as exc:
            messages.error(request, _message(exc))
        return redirect("obtention:journey", pk=journey.pk)


class ObtentionRequirementAssessmentView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, pk, assessment_id):
        journey = _visible_journey(request.user, pk)
        if not can(
            request.user,
            PermissionCode.ACTIVITY_MANAGE,
            activity=journey.activity,
        ):
            from django.http import Http404

            raise Http404
        assessment = get_object_or_404(
            journey.requirement_assessments.select_related(
                "journey__activity",
                "requirement",
            ),
            pk=assessment_id,
        )
        state = (request.POST.get("state") or "").strip()
        if state not in RequirementAssessmentState.values:
            messages.error(request, "État Requirement invalide.")
            return redirect("obtention:journey", pk=journey.pk)
        try:
            assess_journey_requirement(
                assessment=assessment,
                actor=request.user,
                state=state,
                reason_code="obtention_operator_assessment",
                note=(request.POST.get("note") or "").strip(),
            )
        except (PermissionDenied, ValidationError) as exc:
            messages.error(request, _message(exc))
        else:
            messages.success(request, "Condition mise à jour.")
        return redirect("obtention:journey", pk=journey.pk)



class ObtentionOccurrenceCreateView(LoginRequiredMixin, TemplateView):
    template_name = "obtention/occurrence_form.html"
    login_url = "core:login"

    def _obtention(self):
        return _managed_obtention(self.request.user, self.kwargs["pk"])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        obtention = self._obtention()
        context.update(
            {
                "obtention": obtention,
                "activity": obtention.activity,
                "form": kwargs.get("form") or ObtentionOccurrenceForm(),
            }
        )
        return context

    def post(self, request, pk):
        obtention = self._obtention()
        form = ObtentionOccurrenceForm(request.POST)
        if form.is_valid():
            try:
                create_occurrence(
                    activity=obtention.activity,
                    **form.cleaned_data,
                )
            except ValidationError as exc:
                form.add_error(None, _message(exc))
            else:
                messages.success(request, "Occurrence ajoutée.")
                return redirect("obtention:manage", pk=obtention.pk)
        return self.render_to_response(self.get_context_data(form=form), status=400)
