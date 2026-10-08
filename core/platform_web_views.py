"""Web-first operator presentation; all facts and authority belong to owners."""
from datetime import timedelta

from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.http import Http404
from django.shortcuts import redirect
from operations.forms import EventModerationForm, OrganizationReviewForm
from operations.services import change_organization_lifecycle, moderate_event, audit_action
from operations.selectors import get_operations_events
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
        response = super().dispatch(request, *args, **kwargs)
        response["Cache-Control"] = "private, no-store"
        return response

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



class PlatformTrustView(PlatformView):
    module = "trust_review"
    page = "trust"
    heading = "Confiance"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from trust.models import VerificationClaim, Report, Dispute
        context["claims"] = VerificationClaim.objects.filter(
            status__in=["requested", "under_review"]
        ).select_related("subject_space")[:40]
        context["reports"] = Report.objects.filter(
            status__in=["open", "triaged", "investigating"]
        ).select_related("space")[:40]
        context["disputes"] = Dispute.objects.exclude(
            status="closed"
        ).select_related("respondent_space")[:40]
        return context


class PlatformCurationView(PlatformView):
    module = "opportunity_curation"
    page = "curation"
    heading = "Curation"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from services.attention_selectors import opportunity_curator_attention
        attention = opportunity_curator_attention(self.request.user)
        context["submissions"] = attention["submissions"][:30]
        context["sources"] = attention["sources"][:30]
        context["withdrawn"] = attention["withdrawn_with_active_journeys"][:30]
        return context


class PlatformSubscriptionsView(PlatformView):
    module = "subscriptions"
    page = "subscriptions"
    heading = "Gouvernance des abonnements"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        effective = set(next(
            item["capabilities"] for item in self.platform_modules if item["key"] == "subscriptions"
        ))
        context["catalog_allowed"] = bool(effective & {
            PermissionCode.PLATFORM_SUBSCRIPTIONS_CATALOG_VIEW,
            PermissionCode.PLATFORM_SUBSCRIPTIONS_CATALOG_MANAGE,
        })
        context["support_allowed"] = bool(effective & {
            PermissionCode.PLATFORM_SUBSCRIPTIONS_VIEW,
            PermissionCode.PLATFORM_SUBSCRIPTIONS_MANAGE,
        })
        context["review_allowed"] = PermissionCode.PLATFORM_SUBSCRIPTIONS_REVIEWS_MANAGE in effective
        context["grant_allowed"] = PermissionCode.PLATFORM_SUBSCRIPTIONS_GRANTS_MANAGE in effective
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


class PlatformDecisionView(PlatformView):
    """Consequence-first POST-only mutations through canonical Operations services."""
    module = "operations"
    page = "decision"
    template_name = "platform/decision.html"

    def get_subject(self, request):
        raise NotImplementedError

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["subject"] = self.get_subject(self.request)
        context["form"] = self.form_class()
        context["expected_state"] = self.current_state(context["subject"])
        context["impact"] = self.impact
        context["back_url"] = "/platform/operations/"
        return context

    def post(self, request, *args, **kwargs):
        form = self.form_class(request.POST)
        if not form.is_valid() or request.POST.get("confirm") != "1":
            return self.render_to_response(
                {**self.get_context_data(), "form": form,
                 "error_message": "Choisissez une action, donnez une raison et confirmez la conséquence."},
                status=400,
            )
        with transaction.atomic():
            # Lock the owner row before comparing expected state and mutating.
            subject = self.lock_subject(request)
            if not can(request.user, PermissionCode.PLATFORM_MANAGE):
                raise PermissionDenied("Permission Operations révoquée.")
            before = self.current_state(subject)
            if before != request.POST.get("expected_state"):
                return self.render_to_response(
                    {**self.get_context_data(), "form": form,
                     "error_message": "La réalité a changé depuis son ouverture. Actualisez avant de décider."},
                    status=409,
                )
            try:
                result = self.apply_decision(subject, form.cleaned_data, request.user)
            except ValidationError as exc:
                return self.render_to_response(
                    {**self.get_context_data(), "form": form,
                     "error_message": "; ".join(exc.messages)},
                    status=409,
                )
            after = self.current_state(result)
        messages.success(request, f"Action confirmée : {before} → {after}.")
        return redirect(request.path)


class PlatformSpaceDecisionView(PlatformDecisionView):
    heading = "Décision sur un Espace"
    form_class = OrganizationReviewForm
    impact = "Suspendre retire l'Espace de l'activité normale. Archiver le retire des usages courants ; restaurer le rend de nouveau actif selon les règles owner."

    def get_subject(self, request):
        return get_object_or_404(
            get_operations_organizations(request.user), pk=self.kwargs["pk"]
        )

    def lock_subject(self, request):
        from organizations.models import Organization
        return get_object_or_404(
            Organization.objects.select_for_update(), pk=self.kwargs["pk"]
        )

    def current_state(self, subject):
        return subject.lifecycle

    def apply_decision(self, subject, data, actor):
        if subject.lifecycle == data["status"]:
            raise ValidationError("Cette décision est déjà appliquée.")
        result = change_organization_lifecycle(
            organization=subject, status=data["status"], actor=actor,
            reason=data["reason"],
        )
        audit_action(
            actor=actor, action="platform.space_lifecycle_decision",
            target_type="organization", target_id=result.pk,
            summary="Décision de lifecycle via Makolo Platform",
            before={"lifecycle": subject.lifecycle}, after={"lifecycle": result.lifecycle},
            metadata={"reason": data["reason"]},
        )
        return result


class PlatformEventDecisionView(PlatformDecisionView):
    heading = "Modération Event"
    form_class = EventModerationForm
    impact = "Retirer de la découverte ou rendre privé réduit la visibilité ; annuler affecte la réalisation de l'Event ; restaurer la visibilité n'annule pas une annulation métier."

    def get_subject(self, request):
        return get_object_or_404(
            get_operations_events(request.user), pk=self.kwargs["pk"]
        )

    def lock_subject(self, request):
        from events.models import Event
        return get_object_or_404(
            Event.objects.select_for_update(), pk=self.kwargs["pk"]
        )

    def current_state(self, subject):
        return f"{subject.status}:{subject.visibility}"

    def apply_decision(self, subject, data, actor):
        from events.models import EventStatus, EventVisibility
        if ((data["action"] == "unlist" and subject.visibility == EventVisibility.UNLISTED)
            or (data["action"] == "private" and subject.visibility == EventVisibility.PRIVATE)
            or (data["action"] == "cancel" and subject.status == EventStatus.CANCELLED)
            or (data["action"] == "restore_public" and subject.visibility == EventVisibility.PUBLIC)):
            raise ValidationError("Cette décision est déjà appliquée.")
        return moderate_event(
            event=subject, action=data["action"], actor=actor,
            reason=data["reason"],
        )


class PlatformRecognitionActionView(PlatformRecognitionView):
    template_name = "platform/recognition_action.html"
    page = "recognition_action"
    heading = "Décision Recognition"

    def dispatch(self, request, *args, **kwargs):
        self.action = kwargs["action"]
        if self.action not in {"simulate", "publish"}:
            raise Http404
        code = (PermissionCode.PLATFORM_RECOGNITION_POLICY_MANAGE
                if self.action == "simulate" else PermissionCode.PLATFORM_RECOGNITION_POLICY_PUBLISH)
        if not can(request.user, code):
            raise PermissionDenied("Autorité Recognition requise.")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from recognition.models import RecognitionPolicy
        policy = get_object_or_404(RecognitionPolicy, pk=self.kwargs["pk"])
        context.update(
            policy=policy,
            recognition_action=self.action,
            impact=(
                "La simulation enregistre un état simulé sans publication ni attribution de crédits."
                if self.action == "simulate" else
                "La publication active ou planifie la Policy à sa frontière temporelle. Elle peut remplacer la Policy active."
            ),
        )
        return context

    def post(self, request, *args, **kwargs):
        if request.POST.get("confirm") != "1":
            return self.render_to_response(
                {**self.get_context_data(), "error_message": "Confirmation explicite requise."},
                status=400,
            )
        from recognition.governance_services import record_policy_simulation, publish_policy_for_actor
        try:
            if self.action == "simulate":
                result = record_policy_simulation(
                    actor=request.user, policy_id=self.kwargs["pk"],
                    expected_status=request.POST.get("expected_status", ""),
                    reason=request.POST.get("reason", ""),
                )
                messages.success(request, "Simulation enregistrée : %s Signals. Publication inchangée." % result["signals"])
            else:
                result = publish_policy_for_actor(
                    actor=request.user, policy_id=self.kwargs["pk"],
                    expected_status=request.POST.get("expected_status", ""),
                    reason=request.POST.get("reason", ""),
                )
                messages.success(request, "Policy %s ; frontière : %s." % (result["status"], result["effective_from"].isoformat()))
        except ValidationError as exc:
            return self.render_to_response(
                {**self.get_context_data(), "error_message": "; ".join(exc.messages)},
                status=409,
            )
        return redirect("platform_web:recognition")
