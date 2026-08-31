from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Max, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import TemplateView

from authorization.constants import PermissionCode
from authorization.services import can
from requirements.contracts import RequirementAssessmentState, RequirementMode
from subscriptions.authorization import get_subscription_for_actor, subscriptions_visible_to_actor
from subscriptions.contracts import PlanVersionStatus
from subscriptions.eligibility_models import EntitlementRequirement, PlanRequirement
from subscriptions.models import PlanBenefit, PlanEntitlement, PlanVersion, SubscriptionPlan
from subscriptions.product_read import build_subscription_product_view
from subscriptions.review_services import review_subscription_requirement
from subscriptions.runtime_models import EntitlementGrant
from subscriptions.security_services import (
    cancel_subscription_transition_for_actor,
    complete_subscription_transition_for_actor,
    create_entitlement_grant_for_actor,
    revoke_entitlement_grant_for_actor,
)
from subscriptions.services import publish_plan_version, retire_plan_version
from subscriptions.transition_models import SubscriptionRequirementAssessment, SubscriptionTransition

from .subscription_forms import (
    EntitlementGrantForm,
    EntitlementRequirementForm,
    GrantRevokeForm,
    PlanBenefitForm,
    PlanEntitlementForm,
    PlanRequirementForm,
    PlanVersionForm,
    SubscriptionPlanForm,
    SubscriptionReviewForm,
)


CATALOG_VIEW_PERMISSIONS = (
    PermissionCode.PLATFORM_SUBSCRIPTIONS_CATALOG_VIEW,
    PermissionCode.PLATFORM_SUBSCRIPTIONS_CATALOG_MANAGE,
)
SUPPORT_VIEW_PERMISSIONS = (
    PermissionCode.PLATFORM_SUBSCRIPTIONS_VIEW,
    PermissionCode.PLATFORM_SUBSCRIPTIONS_MANAGE,
)
SUBSCRIPTION_OPERATIONS_PERMISSIONS = (
    *CATALOG_VIEW_PERMISSIONS,
    *SUPPORT_VIEW_PERMISSIONS,
    PermissionCode.PLATFORM_SUBSCRIPTIONS_GRANTS_MANAGE,
    PermissionCode.PLATFORM_SUBSCRIPTIONS_REVIEWS_MANAGE,
)


class SubscriptionOperationsPermissionMixin(LoginRequiredMixin):
    login_url = "core:login"
    required_permissions = SUBSCRIPTION_OPERATIONS_PERMISSIONS

    def dispatch(self, request, *args, **kwargs):
        if not any(can(request.user, code) for code in self.required_permissions):
            raise PermissionDenied("Permission plateforme Subscription requise.")
        return super().dispatch(request, *args, **kwargs)


class SubscriptionCatalogViewMixin(SubscriptionOperationsPermissionMixin):
    required_permissions = CATALOG_VIEW_PERMISSIONS


class SubscriptionCatalogManageMixin(SubscriptionOperationsPermissionMixin):
    required_permissions = (PermissionCode.PLATFORM_SUBSCRIPTIONS_CATALOG_MANAGE,)


class SubscriptionSupportViewMixin(SubscriptionOperationsPermissionMixin):
    required_permissions = SUPPORT_VIEW_PERMISSIONS


class SubscriptionSupportManageMixin(SubscriptionOperationsPermissionMixin):
    required_permissions = (PermissionCode.PLATFORM_SUBSCRIPTIONS_MANAGE,)


class OperationsSubscriptionHubView(SubscriptionOperationsPermissionMixin, TemplateView):
    template_name = "operations/subscription_hub.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context.update(
            {
                "can_catalog_view": any(can(user, code) for code in CATALOG_VIEW_PERMISSIONS),
                "can_catalog_manage": can(user, PermissionCode.PLATFORM_SUBSCRIPTIONS_CATALOG_MANAGE),
                "can_support_view": any(can(user, code) for code in SUPPORT_VIEW_PERMISSIONS),
                "can_grants_manage": can(user, PermissionCode.PLATFORM_SUBSCRIPTIONS_GRANTS_MANAGE),
                "can_reviews_manage": can(user, PermissionCode.PLATFORM_SUBSCRIPTIONS_REVIEWS_MANAGE),
            }
        )
        return context


class OperationsSubscriptionCatalogView(SubscriptionCatalogViewMixin, TemplateView):
    template_name = "operations/subscription_catalog.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        plans = SubscriptionPlan.objects.select_related("current_version").prefetch_related("versions").order_by(
            "subject_type", "plan_type", "code"
        )
        context["plans"] = plans
        context["can_manage"] = can(self.request.user, PermissionCode.PLATFORM_SUBSCRIPTIONS_CATALOG_MANAGE)
        context["plan_form"] = SubscriptionPlanForm()
        return context


class OperationsSubscriptionPlanCreateView(SubscriptionCatalogManageMixin, View):
    def post(self, request):
        form = SubscriptionPlanForm(request.POST)
        if form.is_valid():
            plan = form.save(commit=False)
            plan.created_by = request.user
            try:
                plan.save()
            except ValidationError as exc:
                messages.error(request, "; ".join(exc.messages))
            else:
                messages.success(request, "Plan Subscription créé.")
                return redirect("operations:subscription-plan", plan_id=plan.pk)
        else:
            messages.error(request, "Le Plan n’a pas été créé : vérifiez les champs.")
        return redirect("operations:subscription-catalog")


class OperationsSubscriptionPlanView(SubscriptionCatalogViewMixin, TemplateView):
    template_name = "operations/subscription_plan.html"

    def get_plan(self):
        return get_object_or_404(
            SubscriptionPlan.objects.select_related("current_version").prefetch_related("versions"),
            pk=self.kwargs["plan_id"],
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        plan = self.get_plan()
        context.update(
            {
                "plan": plan,
                "can_manage": can(self.request.user, PermissionCode.PLATFORM_SUBSCRIPTIONS_CATALOG_MANAGE),
                "version_form": PlanVersionForm(),
            }
        )
        return context


class OperationsPlanVersionCreateView(SubscriptionCatalogManageMixin, View):
    def post(self, request, plan_id):
        plan = get_object_or_404(SubscriptionPlan, pk=plan_id)
        form = PlanVersionForm(request.POST)
        if form.is_valid():
            highest = plan.versions.aggregate(value=Max("version"))["value"] or 0
            version = form.save(commit=False)
            version.plan = plan
            version.version = highest + 1
            version.created_by = request.user
            try:
                version.save()
            except ValidationError as exc:
                messages.error(request, "; ".join(exc.messages))
            else:
                messages.success(request, f"Draft v{version.version} créé.")
                return redirect("operations:subscription-version", version_id=version.pk)
        else:
            messages.error(request, "La version draft n’a pas été créée.")
        return redirect("operations:subscription-plan", plan_id=plan.pk)


class OperationsPlanVersionView(SubscriptionCatalogViewMixin, TemplateView):
    template_name = "operations/subscription_version.html"

    def get_version(self):
        return get_object_or_404(
            PlanVersion.objects.select_related("plan")
            .prefetch_related(
                "benefits",
                "entitlements__feature",
                "entitlements__requirements",
                "requirements",
            ),
            pk=self.kwargs["version_id"],
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        version = self.get_version()
        can_manage = can(self.request.user, PermissionCode.PLATFORM_SUBSCRIPTIONS_CATALOG_MANAGE)
        editable = can_manage and version.status == PlanVersionStatus.DRAFT
        context.update(
            {
                "version": version,
                "plan": version.plan,
                "can_manage": can_manage,
                "editable": editable,
                "version_form": PlanVersionForm(instance=version),
                "benefit_form": PlanBenefitForm(),
                "entitlement_form": PlanEntitlementForm(plan_version=version),
                "requirement_form": PlanRequirementForm(),
            }
        )
        return context


class OperationsPlanVersionUpdateView(SubscriptionCatalogManageMixin, View):
    def post(self, request, version_id):
        version = get_object_or_404(PlanVersion, pk=version_id, status=PlanVersionStatus.DRAFT)
        form = PlanVersionForm(request.POST, instance=version)
        if form.is_valid():
            try:
                form.save()
            except ValidationError as exc:
                messages.error(request, "; ".join(exc.messages))
            else:
                messages.success(request, "Draft mis à jour.")
        else:
            messages.error(request, "Le draft contient des erreurs.")
        return redirect("operations:subscription-version", version_id=version.pk)


class OperationsPlanBenefitCreateView(SubscriptionCatalogManageMixin, View):
    def post(self, request, version_id):
        version = get_object_or_404(PlanVersion, pk=version_id, status=PlanVersionStatus.DRAFT)
        form = PlanBenefitForm(request.POST)
        if form.is_valid():
            benefit = form.save(commit=False)
            benefit.plan_version = version
            try:
                benefit.save()
            except ValidationError as exc:
                messages.error(request, "; ".join(exc.messages))
            else:
                messages.success(request, "Benefit ajouté.")
        else:
            messages.error(request, "Le Benefit n’a pas été ajouté.")
        return redirect("operations:subscription-version", version_id=version.pk)


class OperationsPlanBenefitDeleteView(SubscriptionCatalogManageMixin, View):
    def post(self, request, version_id, benefit_id):
        version = get_object_or_404(PlanVersion, pk=version_id, status=PlanVersionStatus.DRAFT)
        benefit = get_object_or_404(PlanBenefit, pk=benefit_id, plan_version=version)
        benefit.delete()
        messages.success(request, "Benefit retiré du draft.")
        return redirect("operations:subscription-version", version_id=version.pk)


class OperationsPlanEntitlementCreateView(SubscriptionCatalogManageMixin, View):
    def post(self, request, version_id):
        version = get_object_or_404(PlanVersion.objects.select_related("plan"), pk=version_id, status=PlanVersionStatus.DRAFT)
        form = PlanEntitlementForm(request.POST, plan_version=version)
        if form.is_valid():
            entitlement = PlanEntitlement(
                plan_version=version,
                feature=form.cleaned_data["feature"],
                value=form.cleaned_data["normalized_value"],
            )
            try:
                entitlement.save()
            except ValidationError as exc:
                messages.error(request, "; ".join(exc.messages))
            else:
                messages.success(request, "Entitlement ajouté.")
        else:
            messages.error(request, "L’Entitlement n’a pas été ajouté.")
        return redirect("operations:subscription-version", version_id=version.pk)


class OperationsPlanEntitlementDeleteView(SubscriptionCatalogManageMixin, View):
    def post(self, request, version_id, entitlement_id):
        version = get_object_or_404(PlanVersion, pk=version_id, status=PlanVersionStatus.DRAFT)
        entitlement = get_object_or_404(PlanEntitlement, pk=entitlement_id, plan_version=version)
        entitlement.delete()
        messages.success(request, "Entitlement retiré du draft.")
        return redirect("operations:subscription-version", version_id=version.pk)


class OperationsPlanRequirementCreateView(SubscriptionCatalogManageMixin, View):
    def post(self, request, version_id):
        version = get_object_or_404(PlanVersion.objects.select_related("plan"), pk=version_id, status=PlanVersionStatus.DRAFT)
        form = PlanRequirementForm(request.POST)
        if form.is_valid():
            requirement = PlanRequirement(
                plan_version=version,
                key=form.cleaned_data["key"],
                title=form.cleaned_data["title"],
                description=form.cleaned_data["description"],
                phase=form.cleaned_data["phase"],
                mode=form.cleaned_data["mode"],
                evaluator_key=form.cleaned_data["evaluator_key"],
                config=form.cleaned_data["config"],
                is_mandatory=form.cleaned_data["mandatory"],
                position=form.cleaned_data["position"],
                failure_policy=form.cleaned_data["failure_policy"],
                grace_period_days=form.cleaned_data["grace_period_days"],
                disclosure=form.cleaned_data["disclosure"],
            )
            try:
                requirement.save()
            except ValidationError as exc:
                messages.error(request, "; ".join(exc.messages))
            else:
                messages.success(request, "Requirement ajouté.")
        else:
            messages.error(request, "Le Requirement n’a pas été ajouté.")
        return redirect("operations:subscription-version", version_id=version.pk)


class OperationsPlanRequirementDeleteView(SubscriptionCatalogManageMixin, View):
    def post(self, request, version_id, requirement_id):
        version = get_object_or_404(PlanVersion, pk=version_id, status=PlanVersionStatus.DRAFT)
        requirement = get_object_or_404(PlanRequirement, pk=requirement_id, plan_version=version)
        requirement.delete()
        messages.success(request, "Requirement retiré du draft.")
        return redirect("operations:subscription-version", version_id=version.pk)


class OperationsEntitlementRequirementCreateView(SubscriptionCatalogManageMixin, View):
    def post(self, request, version_id, entitlement_id):
        version = get_object_or_404(PlanVersion, pk=version_id, status=PlanVersionStatus.DRAFT)
        entitlement = get_object_or_404(PlanEntitlement, pk=entitlement_id, plan_version=version)
        form = EntitlementRequirementForm(request.POST)
        if form.is_valid():
            requirement = EntitlementRequirement(
                plan_entitlement=entitlement,
                key=form.cleaned_data["key"],
                title=form.cleaned_data["title"],
                description=form.cleaned_data["description"],
                mode=form.cleaned_data["mode"],
                evaluator_key=form.cleaned_data["evaluator_key"],
                config=form.cleaned_data["config"],
                is_mandatory=form.cleaned_data["mandatory"],
                position=form.cleaned_data["position"],
                disclosure=form.cleaned_data["disclosure"],
            )
            try:
                requirement.save()
            except ValidationError as exc:
                messages.error(request, "; ".join(exc.messages))
            else:
                messages.success(request, "Condition d’Entitlement ajoutée.")
        else:
            messages.error(request, "La condition d’Entitlement n’a pas été ajoutée.")
        return redirect("operations:subscription-version", version_id=version.pk)


class OperationsEntitlementRequirementDeleteView(SubscriptionCatalogManageMixin, View):
    def post(self, request, version_id, entitlement_id, requirement_id):
        version = get_object_or_404(PlanVersion, pk=version_id, status=PlanVersionStatus.DRAFT)
        entitlement = get_object_or_404(PlanEntitlement, pk=entitlement_id, plan_version=version)
        requirement = get_object_or_404(EntitlementRequirement, pk=requirement_id, plan_entitlement=entitlement)
        requirement.delete()
        messages.success(request, "Condition d’Entitlement retirée du draft.")
        return redirect("operations:subscription-version", version_id=version.pk)


class OperationsPlanVersionPublishView(SubscriptionCatalogManageMixin, View):
    def post(self, request, version_id):
        version = get_object_or_404(PlanVersion, pk=version_id)
        try:
            publish_plan_version(version)
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
        else:
            messages.success(request, f"{version.name} est publiée.")
        return redirect("operations:subscription-version", version_id=version.pk)


class OperationsPlanVersionRetireView(SubscriptionCatalogManageMixin, View):
    def post(self, request, version_id):
        version = get_object_or_404(PlanVersion, pk=version_id)
        try:
            retire_plan_version(version)
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
        else:
            messages.success(request, f"{version.name} est retirée du catalogue.")
        return redirect("operations:subscription-version", version_id=version.pk)


class OperationsSubscriptionSupportListView(SubscriptionSupportViewMixin, TemplateView):
    template_name = "operations/subscription_support.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        queryset = subscriptions_visible_to_actor(self.request.user).select_related("profile", "space")
        query = (self.request.GET.get("q") or "").strip()[:120]
        status = (self.request.GET.get("status") or "").strip()
        if query:
            queryset = queryset.filter(
                Q(profile__username__icontains=query)
                | Q(profile__email__icontains=query)
                | Q(space__name__icontains=query)
                | Q(space__slug__icontains=query)
            )
        if status:
            queryset = queryset.filter(status=status)
        paginator = Paginator(queryset.order_by("-updated_at", "id"), 30)
        context.update({"page_obj": paginator.get_page(self.request.GET.get("page")), "query": query, "status_filter": status})
        return context


class OperationsSubscriptionSupportDetailView(SubscriptionSupportViewMixin, TemplateView):
    template_name = "operations/subscription_detail.html"

    def get_subscription(self):
        return get_subscription_for_actor(self.request.user, self.kwargs["subscription_id"])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        subscription = self.get_subscription()
        can_manage = can(self.request.user, PermissionCode.PLATFORM_SUBSCRIPTIONS_MANAGE)
        can_grants = can(self.request.user, PermissionCode.PLATFORM_SUBSCRIPTIONS_GRANTS_MANAGE)
        can_reviews = can(self.request.user, PermissionCode.PLATFORM_SUBSCRIPTIONS_REVIEWS_MANAGE)
        grants = EntitlementGrant.objects.none()
        if can_grants:
            grants = EntitlementGrant.objects.select_related("feature", "granted_by", "revoked_by")
            grants = grants.filter(profile=subscription.profile) if subscription.profile_id else grants.filter(space=subscription.space)
        transitions = SubscriptionTransition.objects.filter(subscription=subscription).select_related(
            "source_plan_version", "target_plan_version", "requested_by"
        ).order_by("-requested_at")[:20]
        pending_reviews = SubscriptionRequirementAssessment.objects.none()
        if can_reviews:
            pending_reviews = (
                SubscriptionRequirementAssessment.objects.filter(
                    transition__subscription=subscription,
                    plan_requirement__mode=RequirementMode.REVIEW,
                    state__in=[RequirementAssessmentState.UNASSESSED, RequirementAssessmentState.PENDING],
                )
                .select_related("plan_requirement", "transition")
                .order_by("created_at")
            )
        context.update(
            {
                "subscription": subscription,
                "product": build_subscription_product_view(subscription, can_manage=can_manage, include_catalog=False),
                "can_manage": can_manage,
                "can_grants": can_grants,
                "can_reviews": can_reviews,
                "grants": grants,
                "transitions": transitions,
                "pending_reviews": pending_reviews,
                "grant_form": EntitlementGrantForm(subscription=subscription),
                "review_form": SubscriptionReviewForm(),
                "revoke_form": GrantRevokeForm(),
            }
        )
        return context


class OperationsEntitlementGrantCreateView(SubscriptionOperationsPermissionMixin, View):
    required_permissions = (PermissionCode.PLATFORM_SUBSCRIPTIONS_GRANTS_MANAGE,)

    def post(self, request, subscription_id):
        subscription = get_subscription_for_actor(request.user, subscription_id)
        form = EntitlementGrantForm(request.POST, subscription=subscription)
        if form.is_valid():
            kwargs = {
                "actor": request.user,
                "feature": form.cleaned_data["feature"],
                "value": form.cleaned_data["normalized_value"],
                "reason": form.cleaned_data["reason"],
                "valid_until": form.cleaned_data["valid_until"],
            }
            if subscription.profile_id:
                kwargs["profile"] = subscription.profile
            else:
                kwargs["space"] = subscription.space
            try:
                create_entitlement_grant_for_actor(**kwargs)
            except ValidationError as exc:
                messages.error(request, "; ".join(exc.messages))
            else:
                messages.success(request, "Grant créé et audité.")
        else:
            messages.error(request, "Le Grant n’a pas été créé.")
        return redirect("operations:subscription-detail", subscription_id=subscription.pk)


class OperationsEntitlementGrantRevokeView(SubscriptionOperationsPermissionMixin, View):
    required_permissions = (PermissionCode.PLATFORM_SUBSCRIPTIONS_GRANTS_MANAGE,)

    def post(self, request, subscription_id, grant_id):
        subscription = get_subscription_for_actor(request.user, subscription_id)
        grants = EntitlementGrant.objects.filter(profile=subscription.profile) if subscription.profile_id else EntitlementGrant.objects.filter(space=subscription.space)
        get_object_or_404(grants, pk=grant_id)
        form = GrantRevokeForm(request.POST)
        if form.is_valid():
            try:
                revoke_entitlement_grant_for_actor(
                    actor=request.user,
                    grant_id=grant_id,
                    reason=form.cleaned_data["reason"],
                )
            except ValidationError as exc:
                messages.error(request, "; ".join(exc.messages))
            else:
                messages.success(request, "Grant révoqué ; son historique est conservé.")
        else:
            messages.error(request, "Une raison de révocation est requise.")
        return redirect("operations:subscription-detail", subscription_id=subscription.pk)


class OperationsSubscriptionReviewQueueView(SubscriptionOperationsPermissionMixin, TemplateView):
    required_permissions = (PermissionCode.PLATFORM_SUBSCRIPTIONS_REVIEWS_MANAGE,)
    template_name = "operations/subscription_reviews.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        queryset = (
            SubscriptionRequirementAssessment.objects.filter(
                plan_requirement__mode=RequirementMode.REVIEW,
                state__in=[RequirementAssessmentState.UNASSESSED, RequirementAssessmentState.PENDING],
            )
            .select_related(
                "plan_requirement",
                "transition__subscription__profile",
                "transition__subscription__space",
                "transition__target_plan_version",
            )
            .order_by("created_at")
        )
        paginator = Paginator(queryset, 30)
        context["page_obj"] = paginator.get_page(self.request.GET.get("page"))
        context["review_form"] = SubscriptionReviewForm()
        return context


class OperationsSubscriptionReviewDecisionView(SubscriptionOperationsPermissionMixin, View):
    required_permissions = (PermissionCode.PLATFORM_SUBSCRIPTIONS_REVIEWS_MANAGE,)

    def post(self, request, assessment_id):
        form = SubscriptionReviewForm(request.POST)
        if form.is_valid():
            try:
                assessment = review_subscription_requirement(
                    actor=request.user,
                    assessment_id=assessment_id,
                    state=form.cleaned_data["state"],
                    reason_code=form.cleaned_data["reason_code"],
                    note=form.cleaned_data["note"],
                )
            except ValidationError as exc:
                messages.error(request, "; ".join(exc.messages))
            else:
                messages.success(request, "Décision de review enregistrée et auditée.")
                return redirect(
                    "operations:subscription-detail",
                    subscription_id=assessment.transition.subscription_id,
                )
        else:
            messages.error(request, "La décision de review est invalide.")
        return redirect("operations:subscription-reviews")


class OperationsSubscriptionTransitionCancelView(SubscriptionSupportManageMixin, View):
    def post(self, request, subscription_id, transition_id):
        subscription = get_subscription_for_actor(request.user, subscription_id, manage=True)
        transition = get_object_or_404(SubscriptionTransition, pk=transition_id, subscription=subscription)
        try:
            cancel_subscription_transition_for_actor(
                actor=request.user,
                transition_id=transition.pk,
                reason="Annulation support via Operations.",
            )
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
        else:
            messages.success(request, "Transition annulée.")
        return redirect("operations:subscription-detail", subscription_id=subscription.pk)


class OperationsSubscriptionTransitionCompleteView(SubscriptionSupportManageMixin, View):
    def post(self, request, subscription_id, transition_id):
        subscription = get_subscription_for_actor(request.user, subscription_id, manage=True)
        transition = get_object_or_404(SubscriptionTransition, pk=transition_id, subscription=subscription)
        try:
            complete_subscription_transition_for_actor(actor=request.user, transition_id=transition.pk)
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
        else:
            messages.success(request, "Transition finalisée selon les invariants S4.")
        return redirect("operations:subscription-detail", subscription_id=subscription.pk)
