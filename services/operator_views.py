from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import TemplateView

from authorization.constants import PermissionCode
from authorization.services import can
from journeys.collaboration_models import (
    JourneyArtifactReview,
    JourneyArtifactReviewStatus,
    JourneyAssignment,
    JourneyBlocker,
    JourneyStep,
)
from journeys.collaboration_services import (
    artifact_for_download,
    assign_journey,
    complete_step,
    create_blocker,
    create_note,
    decide_artifact_review,
    end_journey_assignment,
    resolve_blocker,
    start_artifact_review,
    start_step,
)
from journeys.service_authorization import (
    CASE_SCOPE_VIEW_ALL,
    CASE_SCOPE_VIEW_ASSIGNED,
    service_case_scope,
)
from payments.models import PaymentEvidence
from payments.obligation_services import reject_payment_evidence, verify_payment_evidence

from .attention_selectors import facilitator_attention_journeys, manager_attention_journeys
from .configuration_services import create_intake_question, update_service_details
from .models import ServiceDetails, ServiceIntakeQuestion, ServicePlanTemplate
from .operator_forms import (
    ServiceAssignmentForm,
    ServiceBlockerForm,
    ServiceConfigurationForm,
    ServiceIntakeQuestionForm,
    ServiceNoteForm,
    ServicePlanTemplateForm,
    ServiceReviewDecisionForm,
    ServiceTemplateStepForm,
)
from .selectors import (
    outcome_timeline,
    service_artifacts_visible_to,
    service_journeys_visible_to,
    service_notes_visible_to,
    submissions_for_context,
)
from .services import (
    add_template_step,
    create_plan_template,
    create_plan_template_version,
    publish_plan_template,
    retire_plan_template,
)


PAGE_SIZE = 25
OPERATOR_SCOPES = {CASE_SCOPE_VIEW_ALL, CASE_SCOPE_VIEW_ASSIGNED}


def _operator_journey(actor, pk):
    journey = (
        service_journeys_visible_to(actor)
        .select_related(
            "activity",
            "activity__space",
            "activity__service_details",
            "beneficiary",
            "service_context",
            "service_context__opportunity_revision",
        )
        .filter(pk=pk)
        .first()
    )
    if journey is None or service_case_scope(actor, journey) not in OPERATOR_SCOPES:
        raise Http404
    return journey


def _permission(actor, journey, code):
    return can(actor, code, activity=journey.activity)


def _safe_action(view, action, *, success_message):
    try:
        action()
    except (ValidationError, PermissionDenied) as exc:
        messages.error(view.request, "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc))
    else:
        messages.success(view.request, success_message)


class ServiceOperatorDashboardView(LoginRequiredMixin, TemplateView):
    template_name = "services/operator_dashboard.html"
    login_url = "core:login"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        actor = self.request.user
        queryset = service_journeys_visible_to(actor).exclude(beneficiary=actor)
        q = (self.request.GET.get("q") or "").strip()[:120]
        if q:
            queryset = queryset.filter(
                Q(activity__title__icontains=q)
                | Q(service_context__objective__icontains=q)
                | Q(beneficiary__email__icontains=q)
                | Q(beneficiary__first_name__icontains=q)
                | Q(beneficiary__last_name__icontains=q)
            )
        attention_ids = facilitator_attention_journeys(actor).values("pk").union(
            manager_attention_journeys(actor).values("pk")
        )
        if self.request.GET.get("attention") == "1":
            queryset = queryset.filter(pk__in=attention_ids)
        queryset = queryset.select_related("activity", "beneficiary", "service_context").distinct()
        context.update(
            {
                "page_obj": Paginator(queryset, PAGE_SIZE).get_page(self.request.GET.get("page")),
                "attention_count": service_journeys_visible_to(actor).exclude(beneficiary=actor).filter(pk__in=attention_ids).count(),
                "query": q,
                "attention_only": self.request.GET.get("attention") == "1",
            }
        )
        return context


class ServiceOperatorCaseView(LoginRequiredMixin, TemplateView):
    template_name = "services/operator_case.html"
    login_url = "core:login"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        journey = _operator_journey(self.request.user, kwargs["pk"])
        artifacts = service_artifacts_visible_to(self.request.user, journey=journey).prefetch_related("reviews")
        notes = service_notes_visible_to(self.request.user, journey=journey)
        service_context = journey.service_context
        context.update(
            {
                "journey": journey,
                "case_scope": service_case_scope(self.request.user, journey),
                "steps": journey.steps.select_related("occurrence").prefetch_related("dependencies__depends_on").all(),
                "blockers": journey.blockers.select_related("step", "responsible_profile").all(),
                "assignments": journey.assignments.select_related("profile").all(),
                "artifacts": artifacts,
                "notes": notes,
                "obligations": journey.payment_obligations.prefetch_related("evidence").all(),
                "submissions": submissions_for_context(service_context),
                "outcomes": outcome_timeline(service_context),
                "can_manage_case": _permission(self.request.user, journey, PermissionCode.ACTIVITY_SERVICES_CASES_MANAGE),
                "can_manage_steps": _permission(self.request.user, journey, PermissionCode.ACTIVITY_SERVICES_STEPS_MANAGE),
                "can_manage_blockers": _permission(self.request.user, journey, PermissionCode.ACTIVITY_SERVICES_BLOCKERS_MANAGE),
                "can_manage_assignments": _permission(self.request.user, journey, PermissionCode.ACTIVITY_SERVICES_ASSIGNMENTS_MANAGE),
                "can_manage_notes": _permission(self.request.user, journey, PermissionCode.ACTIVITY_SERVICES_NOTES_INTERNAL),
                "can_review": _permission(self.request.user, journey, PermissionCode.ACTIVITY_SERVICES_REVIEWS_MANAGE),
                "can_verify_evidence": _permission(self.request.user, journey, PermissionCode.ACTIVITY_SERVICES_PAYMENT_EVIDENCE_VERIFY),
                "note_form": ServiceNoteForm(),
                "blocker_form": ServiceBlockerForm(),
                "assignment_form": ServiceAssignmentForm(),
            }
        )
        return context


class _CaseActionView(LoginRequiredMixin, View):
    login_url = "core:login"

    def journey(self):
        return _operator_journey(self.request.user, self.kwargs["pk"])

    def done(self):
        return redirect("services:operator-case", pk=self.kwargs["pk"])


class ServiceStepStartView(_CaseActionView):
    def post(self, request, *args, **kwargs):
        journey = self.journey()
        step = get_object_or_404(JourneyStep, pk=kwargs["step_pk"], journey=journey)
        _safe_action(self, lambda: start_step(step=step, actor=request.user), success_message="Étape démarrée.")
        return self.done()


class ServiceStepCompleteView(_CaseActionView):
    def post(self, request, *args, **kwargs):
        journey = self.journey()
        step = get_object_or_404(JourneyStep, pk=kwargs["step_pk"], journey=journey)
        _safe_action(self, lambda: complete_step(step=step, actor=request.user), success_message="Étape terminée.")
        return self.done()


class ServiceBlockerCreateView(_CaseActionView):
    def post(self, request, *args, **kwargs):
        journey = self.journey()
        form = ServiceBlockerForm(request.POST)
        if form.is_valid():
            values = form.cleaned_data
            _safe_action(
                self,
                lambda: create_blocker(
                    journey=journey,
                    actor=request.user,
                    title=values["title"],
                    category=values["category"],
                    severity=values["severity"],
                    description=values["description"],
                    due_at=values["due_at"],
                ),
                success_message="Blocage ajouté.",
            )
        else:
            messages.error(request, "Le blocage n'a pas pu être enregistré.")
        return self.done()


class ServiceBlockerResolveView(_CaseActionView):
    def post(self, request, *args, **kwargs):
        journey = self.journey()
        blocker = get_object_or_404(JourneyBlocker, pk=kwargs["blocker_pk"], journey=journey)
        waive = request.POST.get("waive") == "1"
        _safe_action(
            self,
            lambda: resolve_blocker(
                blocker=blocker,
                actor=request.user,
                resolution_note=(request.POST.get("resolution_note") or "").strip(),
                waive=waive,
            ),
            success_message="Blocage clôturé.",
        )
        return self.done()


class ServiceNoteCreateView(_CaseActionView):
    def post(self, request, *args, **kwargs):
        journey = self.journey()
        form = ServiceNoteForm(request.POST)
        if form.is_valid():
            _safe_action(
                self,
                lambda: create_note(
                    journey=journey,
                    author=request.user,
                    body=form.cleaned_data["body"],
                    visibility=form.cleaned_data["visibility"],
                ),
                success_message="Note ajoutée.",
            )
        else:
            messages.error(request, "La note n'a pas pu être enregistrée.")
        return self.done()


class ServiceAssignmentCreateView(_CaseActionView):
    def post(self, request, *args, **kwargs):
        journey = self.journey()
        form = ServiceAssignmentForm(request.POST)
        if form.is_valid():
            values = form.cleaned_data
            _safe_action(
                self,
                lambda: assign_journey(
                    journey=journey,
                    profile=values["profile"],
                    responsibility=values["responsibility"],
                    assigned_by=request.user,
                    is_primary=values["is_primary"],
                    replace_primary=values["replace_primary"],
                ),
                success_message="Responsabilité affectée.",
            )
        else:
            messages.error(request, "L'affectation n'a pas pu être enregistrée.")
        return self.done()


class ServiceAssignmentEndView(_CaseActionView):
    def post(self, request, *args, **kwargs):
        journey = self.journey()
        assignment = get_object_or_404(JourneyAssignment, pk=kwargs["assignment_pk"], journey=journey)
        _safe_action(
            self,
            lambda: end_journey_assignment(assignment=assignment, actor=request.user),
            success_message="Responsabilité terminée.",
        )
        return self.done()


class ServiceReviewerQueueView(LoginRequiredMixin, TemplateView):
    template_name = "services/reviewer_queue.html"
    login_url = "core:login"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        visible = service_journeys_visible_to(self.request.user).exclude(beneficiary=self.request.user)
        reviews = (
            JourneyArtifactReview.objects.filter(
                reviewer=self.request.user,
                artifact__journey__in=visible,
                status__in={JourneyArtifactReviewStatus.REQUESTED, JourneyArtifactReviewStatus.IN_PROGRESS},
            )
            .select_related("artifact", "artifact__journey", "artifact__journey__activity", "artifact__journey__beneficiary")
            .order_by("requested_at", "id")
        )
        context["page_obj"] = Paginator(reviews, PAGE_SIZE).get_page(self.request.GET.get("page"))
        return context


class ServiceReviewDecisionView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, *args, **kwargs):
        review = get_object_or_404(
            JourneyArtifactReview.objects.select_related("artifact__journey"),
            pk=kwargs["review_pk"],
            reviewer=request.user,
        )
        journey = _operator_journey(request.user, review.artifact.journey_id)
        form = ServiceReviewDecisionForm(request.POST)
        if form.is_valid():
            decision = form.cleaned_data["decision"]

            def action():
                if review.status == JourneyArtifactReviewStatus.REQUESTED:
                    start_artifact_review(review=review, actor=request.user)
                    review.refresh_from_db()
                decide_artifact_review(
                    review=review,
                    actor=request.user,
                    decision=decision,
                    comment=form.cleaned_data["comment"],
                )

            _safe_action(self, action, success_message="Revue enregistrée.")
        else:
            messages.error(request, "La décision de revue est invalide.")
        return redirect("services:operator-case", pk=journey.pk)


class ServicePaymentEvidenceDecisionView(_CaseActionView):
    def post(self, request, *args, **kwargs):
        journey = self.journey()
        evidence = get_object_or_404(PaymentEvidence, pk=kwargs["evidence_pk"], obligation__journey=journey)
        decision = request.POST.get("decision")
        review_note = (request.POST.get("review_note") or "").strip()
        if decision == "verify":
            action = lambda: verify_payment_evidence(evidence=evidence, actor=request.user, review_note=review_note)
            success = "Preuve de paiement vérifiée."
        elif decision == "reject":
            action = lambda: reject_payment_evidence(evidence=evidence, actor=request.user, review_note=review_note)
            success = "Preuve de paiement rejetée."
        else:
            messages.error(request, "Décision de paiement invalide.")
            return self.done()
        _safe_action(self, action, success_message=success)
        return self.done()


class ServiceArtifactDownloadView(LoginRequiredMixin, View):
    login_url = "core:login"

    def get(self, request, *args, **kwargs):
        try:
            artifact = artifact_for_download(actor=request.user, artifact_id=kwargs["artifact_pk"])
        except PermissionDenied as exc:
            raise Http404 from exc
        if artifact is None or not artifact.file:
            raise Http404
        return FileResponse(artifact.file.open("rb"), as_attachment=True, filename=f"{artifact.title or 'document'}-v{artifact.version}")


class ServiceConfigurationView(LoginRequiredMixin, TemplateView):
    template_name = "services/operator_service_config.html"
    login_url = "core:login"

    def _service(self):
        service = get_object_or_404(ServiceDetails.objects.select_related("activity", "activity__space"), pk=self.kwargs["service_pk"])
        if not can(self.request.user, PermissionCode.ACTIVITY_SERVICES_CONFIGURE, activity=service.activity):
            raise PermissionDenied("La configuration de ce Service n'est pas autorisée.")
        return service

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        service = self._service()
        context.update(
            {
                "service": service,
                "configuration_form": ServiceConfigurationForm(
                    initial={
                        "service_kind": service.service_kind,
                        "opportunity_policy": service.opportunity_policy,
                        "intake_policy": service.intake_policy,
                        "allows_external_beneficiary": service.allows_external_beneficiary,
                        "completion_policy": service.completion_policy,
                    }
                ),
                "template_form": ServicePlanTemplateForm(),
                "step_form": ServiceTemplateStepForm(),
                "intake_form": ServiceIntakeQuestionForm(),
                "templates": service.plan_templates.prefetch_related("steps__dependencies__depends_on").all(),
                "intake_questions": ServiceIntakeQuestion.objects.filter(service=service).order_by("position", "id"),
            }
        )
        return context

    def post(self, request, *args, **kwargs):
        service = self._service()
        action = request.POST.get("action")
        try:
            if action == "update-service":
                form = ServiceConfigurationForm(request.POST)
                if not form.is_valid():
                    raise ValidationError("Configuration Services invalide.")
                update_service_details(service=service, actor=request.user, **form.cleaned_data)
                messages.success(request, "Configuration Services enregistrée.")
            elif action == "create-template":
                form = ServicePlanTemplateForm(request.POST)
                if not form.is_valid():
                    raise ValidationError("Template invalide.")
                create_plan_template(service=service, actor=request.user, **form.cleaned_data)
                messages.success(request, "Template créé en brouillon.")
            elif action == "add-step":
                template = get_object_or_404(ServicePlanTemplate, pk=request.POST.get("template_id"), service=service)
                form = ServiceTemplateStepForm(request.POST)
                if not form.is_valid():
                    raise ValidationError("Étape de template invalide.")
                add_template_step(template=template, actor=request.user, **form.cleaned_data)
                messages.success(request, "Étape ajoutée au template.")
            elif action == "publish-template":
                template = get_object_or_404(ServicePlanTemplate, pk=request.POST.get("template_id"), service=service)
                publish_plan_template(template=template, actor=request.user)
                messages.success(request, "Template publié.")
            elif action == "retire-template":
                template = get_object_or_404(ServicePlanTemplate, pk=request.POST.get("template_id"), service=service)
                retire_plan_template(template=template, actor=request.user)
                messages.success(request, "Template retiré.")
            elif action == "version-template":
                template = get_object_or_404(ServicePlanTemplate, pk=request.POST.get("template_id"), service=service)
                create_plan_template_version(template=template, actor=request.user)
                messages.success(request, "Nouvelle version brouillon créée.")
            elif action == "create-intake":
                form = ServiceIntakeQuestionForm(request.POST)
                if not form.is_valid():
                    raise ValidationError("Question Intake invalide.")
                create_intake_question(service=service, actor=request.user, **form.cleaned_data)
                messages.success(request, "Question Intake ajoutée.")
            else:
                raise ValidationError("Action de configuration inconnue.")
        except (ValidationError, PermissionDenied) as exc:
            messages.error(request, "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc))
        return redirect("services:operator-service-config", service_pk=service.pk)
