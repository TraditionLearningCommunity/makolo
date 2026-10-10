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
from interoperability.presentation import present_connection
from interoperability.projections import build_interoperability_payload
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
        if not request.user.is_authenticated:
            return self.handle_no_permission()
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
        from core.platform_system_projection import operator_event_status
        context["domain_events"] = operator_event_status(self.request.user)
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
    """Permission-first owner federation; never retrieve unscoped Profile/PII."""
    module = None
    page = "investigate"
    heading = "Investiguer"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        q = (self.request.GET.get("q") or "").strip()[:100]
        context["query"] = q
        allowed = {item["key"] for item in self.platform_modules}
        context["operations_search_allowed"] = "operations" in allowed
        context["can_opportunity_merge"] = can(self.request.user, PermissionCode.OPPORTUNITIES_MERGE)
        if q:
            if "operations" in allowed:
                context["investigation_spaces"] = get_operations_organizations(self.request.user).filter(
                    slug__icontains=q
                )[:20]
                context["investigation_incidents"] = get_operations_incidents(self.request.user).filter(
                    title__icontains=q
                ).order_by("-created_at")[:20]
                context["investigation_events"] = get_operations_events(self.request.user).filter(
                    title__icontains=q
                )[:20]
            if "opportunity_curation" in allowed:
                from opportunities.models import Opportunity
                context["investigation_opportunities"] = Opportunity.objects.filter(
                    current_revision__title__icontains=q
                ).select_related("current_revision")[:20]
            if "recognition_governance" in allowed:
                from recognition.models import RecognitionPolicy
                context["investigation_policies"] = RecognitionPolicy.objects.filter(
                    name__icontains=q
                )[:20]
        context["coverage"] = (
            "Recherche owner-fédérée partielle : Operations (Space slug, Event ou incident), "
            "Opportunity et Recognition selon permission. Aucun Profile, Payment, Evidence, "
            "Credential ou contenu privé n'est indexé."
        )
        return context



class PlatformSpaceInvestigationView(PlatformView):
    module = "operations"
    page = "investigation_detail"
    heading = "Investigation Space"
    template_name = "platform/investigation_detail.html"

    def get_context_data(self, **kwargs):
        from operations.selectors import get_moderation_cases
        from activities.models import Activity
        context = super().get_context_data(**kwargs)
        space = get_object_or_404(get_operations_organizations(self.request.user), pk=self.kwargs["pk"])
        context.update(
            target_kind="space",
            target=space,
            target_state=space.get_lifecycle_display(),
            activity_rows=Activity.objects.filter(space=space).only("id", "title", "status")[:30],
            event_rows=get_operations_events(self.request.user).filter(organization=space)[:30],
            incident_rows=get_operations_incidents(self.request.user).filter(organization=space)[:30],
            moderation_rows=get_moderation_cases(self.request.user).filter(organization=space)[:30],
            audit_rows=get_operations_audit_logs(self.request.user).filter(
                target_type="organization", target_id=str(space.pk)
            ).order_by("-created_at")[:30],
        )
        if can(self.request.user, PermissionCode.PLATFORM_TRUST_REVIEW):
            from trust.models import VerificationClaim, Report
            context["trust_claims"] = VerificationClaim.objects.filter(subject_space=space)[:20]
            context["trust_reports"] = Report.objects.filter(space=space)[:20]
        if can(self.request.user, PermissionCode.PLATFORM_SUBSCRIPTIONS_VIEW):
            from subscriptions.runtime_models import Subscription
            context["space_subscription"] = Subscription.objects.filter(space=space).first()
        return context


class PlatformEventInvestigationView(PlatformView):
    module = "operations"
    page = "investigation_detail"
    heading = "Investigation Event"

    template_name = "platform/investigation_detail.html"

    def get_context_data(self, **kwargs):
        from operations.selectors import get_moderation_cases
        from activities.models import Occurrence
        context = super().get_context_data(**kwargs)
        event = get_object_or_404(get_operations_events(self.request.user), pk=self.kwargs["pk"])
        context.update(
            target_kind="event",
            target=event,
            target_state=f"{event.status} · {event.visibility}",
            occurrence_rows=Occurrence.objects.filter(
                activity_id=event.activity_id
            ).order_by("-start_date", "-start_time")[:30],
            incident_rows=get_operations_incidents(self.request.user).filter(
                event=event
            )[:30],
            moderation_rows=get_moderation_cases(self.request.user).filter(event=event)[:30],
            audit_rows=get_operations_audit_logs(self.request.user).filter(
                target_type="event", target_id=str(event.pk)
            ).order_by("-created_at")[:30],
        )
        return context


class PlatformInteroperabilityView(PlatformView):
    module = "interoperability"
    page = "interoperability"
    heading = "Interopérabilité"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from intelligence.interoperability import (
            platform_provider_connections,
            project_provider_connection,
        )

        connections = [
            project_provider_connection(item, manageable=True)
            for item in platform_provider_connections()
        ]
        context["interoperability"] = build_interoperability_payload(
            context="platform",
            connections=connections,
            self_link="/api/v1/platform/interoperability/",
            actor=self.request.user,
            authority_context="platform",
        )
        context["connections"] = [present_connection(row) for row in connections]
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
        context["can_opportunity_merge"] = can(self.request.user, PermissionCode.OPPORTUNITIES_MERGE)
        context["submissions"] = attention["submissions"][:30]
        context["sources"] = attention["sources"][:30]
        context["withdrawn"] = attention["withdrawn_with_active_journeys"][:30]
        return context



class PlatformOpportunityMergeView(PlatformCurationView):
    page = "opportunity_merge"
    heading = "Fusionner deux Opportunities"
    template_name = "platform/opportunity_merge.html"

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not can(request.user, PermissionCode.OPPORTUNITIES_MERGE):
            raise PermissionDenied("Autorité de fusion Opportunity requise.")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        from opportunities.models import Opportunity, OpportunityPublicationStatus
        context = super().get_context_data(**kwargs)
        canonical = get_object_or_404(Opportunity.objects.select_related("current_revision"), pk=self.kwargs["pk"])
        context["canonical"] = canonical
        candidates = Opportunity.objects.exclude(
            publication_status=OpportunityPublicationStatus.MERGED
        ).exclude(pk=canonical.pk).select_related("current_revision")
        query = (self.request.GET.get("q") or "").strip()[:100]
        if query:
            candidates = candidates.filter(current_revision__title__icontains=query)
        context["query"] = query
        context["candidates"] = [
            {"id": str(item.pk), "version": item.updated_at.isoformat(),
             "label": item.current_revision.title if item.current_revision else str(item.pk)}
            for item in candidates[:100]
        ]
        context["canonical_version"] = canonical.updated_at.isoformat()
        return context

    def post(self, request, *args, **kwargs):
        from opportunities.models import Opportunity, OpportunityPublicationStatus
        from opportunities.services import merge_opportunities
        from django import forms
        class DecisionForm(forms.Form):
            duplicate = forms.CharField(max_length=240)
            expected_canonical = forms.CharField(max_length=180)
            reason = forms.CharField(min_length=5, max_length=2000)
            confirm = forms.BooleanField()
        form = DecisionForm(request.POST)
        if not form.is_valid():
            return self.render_to_response(
                {**self.get_context_data(), "error_message": "Fusion, motif et confirmation explicite requis."},
                status=400,
            )
        data = form.cleaned_data
        try:
            from uuid import UUID
            duplicate_id, duplicate_version = data["duplicate"].split("|", 1)
            duplicate_id = UUID(duplicate_id)
        except (ValueError, AttributeError):
            return self.render_to_response(
                {**self.get_context_data(), "error_message": "Choisissez un doublon valide dans la liste."},
                status=400,
            )
        if duplicate_id == self.kwargs["pk"]:
            return self.render_to_response(
                {**self.get_context_data(), "error_message": "Survivant et doublon doivent être différents."},
                status=400,
            )
        with transaction.atomic():
            locked = list(Opportunity.objects.select_for_update().filter(
                pk__in=(self.kwargs["pk"], duplicate_id)
            ).order_by("pk"))
            objects = {row.pk: row for row in locked}
            canonical = objects.get(self.kwargs["pk"])
            duplicate = objects.get(duplicate_id)
            if not canonical or not duplicate:
                raise Http404
            if not can(request.user, PermissionCode.OPPORTUNITIES_MERGE):
                raise PermissionDenied("Autorité de fusion révoquée.")
            if (str(canonical.updated_at.isoformat()) != data["expected_canonical"]
                or str(duplicate.updated_at.isoformat()) != duplicate_version
                or canonical.publication_status == OpportunityPublicationStatus.MERGED
                or duplicate.publication_status == OpportunityPublicationStatus.MERGED):
                return self.render_to_response(
                    {**self.get_context_data(), "error_message": "Les Opportunities ont changé ; actualisez avant la fusion."},
                    status=409,
                )
            try:
                merged = merge_opportunities(canonical=canonical, duplicate=duplicate, actor=request.user)
            except ValidationError as exc:
                return self.render_to_response(
                    {**self.get_context_data(), "error_message": "; ".join(exc.messages)},
                    status=409,
                )
            audit_action(
                actor=request.user, action="opportunity.merge_decision",
                target_type="opportunity", target_id=duplicate.pk,
                summary="Fusion Opportunity confirmée",
                before={"duplicate": str(duplicate.pk), "status": duplicate.publication_status},
                after={"survivor": str(canonical.pk), "status": merged.publication_status},
                metadata={"reason": data["reason"]},
            )
        messages.success(request, "Fusion confirmée par le domaine Opportunity.")
        return redirect("platform_web:curation")


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
        # Query each owner only after its dedicated Permission. No fallback
        # to personal/Space subscription authority for a Platform view.
        if context["catalog_allowed"]:
            from subscriptions.models import SubscriptionPlan
            context["subscription_plans"] = (
                SubscriptionPlan.objects.select_related("current_version")
                .order_by("subject_type", "code")[:30]
            )
        if context["support_allowed"]:
            from subscriptions.runtime_models import Subscription
            context["subscription_rows"] = (
                Subscription.objects.select_related("space")
                .order_by("-created_at")[:40]
            )
        if context["review_allowed"]:
            from subscriptions.transition_models import SubscriptionRequirementAssessment
            from requirements.contracts import RequirementAssessmentState, RequirementMode
            context["subscription_reviews"] = (
                SubscriptionRequirementAssessment.objects.filter(
                    plan_requirement__mode=RequirementMode.REVIEW,
                    state__in=[RequirementAssessmentState.UNASSESSED, RequirementAssessmentState.PENDING],
                ).select_related("transition", "plan_requirement")
                .order_by("created_at")[:30]
            )
        return context


class PlatformRecognitionView(PlatformView):
    module = "recognition_governance"
    page = "recognition"
    heading = "Gouvernance Recognition"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from recognition.models import (
            AchievementDefinition, RecognitionLedgerEntry, RecognitionPolicy, RewardDefinition,
        )
        actor = self.request.user
        context["can_simulate"] = can(actor, PermissionCode.PLATFORM_RECOGNITION_POLICY_MANAGE)
        context["can_publish"] = can(actor, PermissionCode.PLATFORM_RECOGNITION_POLICY_PUBLISH)
        context["policy_allowed"] = (
            can(actor, PermissionCode.PLATFORM_RECOGNITION_VIEW)
            or context["can_simulate"] or context["can_publish"]
        )
        context["rewards_allowed"] = can(actor, PermissionCode.PLATFORM_RECOGNITION_ECONOMY_MANAGE)
        context["achievements_allowed"] = can(actor, PermissionCode.PLATFORM_RECOGNITION_ACHIEVEMENTS_MANAGE)
        context["audit_allowed"] = can(actor, PermissionCode.PLATFORM_RECOGNITION_AUDIT_VIEW)
        if context["policy_allowed"]:
            context["policies"] = RecognitionPolicy.objects.all()[:80]
        if context["rewards_allowed"]:
            context["rewards"] = RewardDefinition.objects.all()[:60]
        if context["achievements_allowed"]:
            context["achievements"] = AchievementDefinition.objects.all()[:60]
        if context["audit_allowed"]:
            context["recognition_ledger"] = (
                RecognitionLedgerEntry.objects.select_related("actor_profile")
                .order_by("-created_at")[:50]
            )
            from operations.models import OperationsAuditLog
            context["recognition_actions"] = (
                OperationsAuditLog.objects.filter(action__startswith="recognition.")
                .select_related("actor").order_by("-created_at")[:50]
            )
        return context


class PlatformRecognitionSimulationView(PlatformRecognitionView):
    page = "recognition_simulation"
    heading = "Simulation Recognition"

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
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
        from activities.models import Activity
        from events.models import Event
        event = get_object_or_404(
            Event.objects.select_for_update(), pk=self.kwargs["pk"]
        )
        # Event status and visibility belong to Activity, not the Event row.
        event.activity = Activity.objects.select_for_update().get(pk=event.activity_id)
        return event

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
        if not request.user.is_authenticated:
            return self.handle_no_permission()
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
        from recognition.models import PolicyStatus, RecognitionCursor
        from recognition.governance_services import _boundary
        current = RecognitionPolicy.objects.filter(status=PolicyStatus.ACTIVE).exclude(
            pk=policy.pk
        ).order_by("-effective_from").first()
        cursor = RecognitionCursor.objects.filter(pk="recognition-v1").first()
        now = timezone.now()
        proposed = max(now, policy.effective_from or now)
        context["active_policy"] = current
        context["publication_boundary"] = (
            _boundary(cursor=cursor, target=proposed) if cursor else proposed
        )
        context["publication_requires_schedule"] = bool(cursor or policy.effective_from and policy.effective_from > now)
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


class PlatformRecognitionAvailabilityView(PlatformView):
    """Govern only availability of Recognition definitions, via owner service."""
    module = "recognition_governance"
    page = "recognition_availability"
    heading = "Disponibilité Recognition"
    template_name = "platform/recognition_availability.html"

    def _definition(self):
        from recognition.models import AchievementDefinition, RewardDefinition
        classes = {
            "reward": (RewardDefinition, PermissionCode.PLATFORM_RECOGNITION_ECONOMY_MANAGE),
            "achievement": (AchievementDefinition, PermissionCode.PLATFORM_RECOGNITION_ACHIEVEMENTS_MANAGE),
        }
        if self.kwargs["kind"] not in classes:
            raise Http404
        model, permission = classes[self.kwargs["kind"]]
        if not can(self.request.user, permission):
            raise PermissionDenied("Permission Recognition spécialisée requise.")
        return get_object_or_404(model, pk=self.kwargs["pk"])

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        self._definition()
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        obj = self._definition()
        context.update(
            definition=obj, kind=self.kwargs["kind"],
            expected_version=obj.updated_at.isoformat(),
            error_message=kwargs.get("error_message", ""),
        )
        return context

    def post(self, request, *args, **kwargs):
        reason = (request.POST.get("reason") or "").strip()
        if request.POST.get("confirm") != "1" or request.POST.get("activate") not in {"0", "1"}:
            return self.render_to_response(self.get_context_data(
                error_message="Confirmation explicite et disponibilité cible requises."
            ), status=400)
        from recognition.governance_services import change_recognition_definition_availability
        try:
            obj = change_recognition_definition_availability(
                actor=request.user, kind=self.kwargs["kind"],
                definition_id=self.kwargs["pk"],
                expected_version=request.POST.get("expected_version", ""),
                activate=request.POST["activate"] == "1",
                reason=reason,
            )
        except ValidationError as exc:
            return self.render_to_response(self.get_context_data(
                error_message="; ".join(exc.messages)
            ), status=409)
        messages.success(request, f"Disponibilité mise à jour pour {obj.name}. Motif enregistré.")
        return redirect("platform_web:recognition")
