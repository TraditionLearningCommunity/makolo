from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views import View
from django.views.generic import TemplateView

from activities.models import Activity
from discovery.recommendations import activity_destination
from groups.models import Group
from notifications.models import NotificationCategory, NotificationKind
from notifications.services import create_notification
from organizations.models import Organization

from .action_stream import build_action_stream
from .bilateral_services import (
    can_manage_action_need,
    cancel_action_proposal,
    close_action_need,
    create_action_need,
    create_action_proposal,
    respond_to_action_proposal,
)
from .forms import ActionNeedForm
from .models import (
    ActionNeed,
    ActionNeedStatus,
    ActionProposal,
    ActionProposalDirection,
    ActionProposalStatus,
    Contribution,
    ContributionKind,
    ContributionStatus,
)
from .profile_search import (
    action_needs_for_actor,
    proposals_for_profile,
    search_profiles_for_need,
    search_spaces_for_need,
)
from .selectors import group_contributions
from .services import create_contribution, moderate_contribution, share_activity_to_group


User = get_user_model()


class NetworkView(LoginRequiredMixin, TemplateView):
    template_name = "social/network.html"
    login_url = "core:login"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            offset = max(0, int(self.request.GET.get("offset", "0")))
        except ValueError:
            offset = 0
        context["stream_page"] = build_action_stream(self.request.user, offset=offset, limit=20)
        return context


class GroupNetworkView(LoginRequiredMixin, TemplateView):
    template_name = "social/group_network.html"
    login_url = "core:login"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        group = get_object_or_404(Group.objects.select_related("space", "owner_profile"), slug=self.kwargs["slug"])
        context["group"] = group
        context["contributions"] = group_contributions(viewer=self.request.user, group=group, limit=50)
        context["shareable_activities"] = Activity.objects.filter(status="published", visibility="public").order_by("-updated_at")[:30]
        return context


class GroupContributeView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, slug):
        group = get_object_or_404(Group, slug=slug)
        try:
            create_contribution(actor=request.user, kind=ContributionKind.DISCUSSION, body=request.POST.get("body", ""), group=group)
        except (ValidationError, PermissionDenied) as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Contribution publiée dans le Groupe.")
        return redirect("social:group", slug=group.slug)


class GroupShareActivityView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, slug):
        group = get_object_or_404(Group, slug=slug)
        activity = get_object_or_404(Activity, pk=request.POST.get("activity_id"))
        try:
            share_activity_to_group(actor=request.user, group=group, activity=activity, body=request.POST.get("body", ""))
        except (ValidationError, PermissionDenied) as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Activity partagée dans le Groupe sans transfert de droits.")
        return redirect("social:group", slug=group.slug)


class ReplyContributionView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, pk):
        parent = get_object_or_404(Contribution.objects.select_related("group", "author_profile"), pk=pk)
        try:
            reply = create_contribution(actor=request.user, kind=ContributionKind.DISCUSSION, body=request.POST.get("body", ""), parent=parent)
        except (ValidationError, PermissionDenied) as exc:
            messages.error(request, str(exc))
        else:
            if parent.author_profile_id != request.user.pk:
                create_notification(
                    recipient=parent.author_profile,
                    kind=NotificationKind.SYSTEM,
                    category=NotificationCategory.SYSTEM,
                    title="Nouvelle réponse dans Makolo",
                    message="Une personne a répondu à votre contribution dans son contexte Makolo.",
                    action_url=reverse("social:group", kwargs={"slug": parent.group.slug}) if parent.group_id else reverse("social:network"),
                    dedup_key=f"social-reply:{reply.pk}",
                    metadata={"contribution_id": str(parent.pk)},
                    queue_email=False,
                )
            messages.success(request, "Réponse publiée.")
        if parent.group_id:
            return redirect("social:group", slug=parent.group.slug)
        return redirect("social:network")


class RemoveContributionView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, pk):
        contribution = get_object_or_404(Contribution, pk=pk)
        try:
            moderate_contribution(actor=request.user, contribution=contribution, status=ContributionStatus.REMOVED)
        except PermissionDenied:
            raise PermissionDenied("Vous ne pouvez pas retirer cette Contribution.")
        if contribution.group_id:
            return redirect("social:group", slug=contribution.group.slug)
        return redirect("social:network")


class ActionNeedsView(LoginRequiredMixin, TemplateView):
    template_name = "social/action_needs.html"
    login_url = "core:login"

    def _form(self, data=None):
        return ActionNeedForm(data=data, actor=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form"] = kwargs.get("form") or self._form()
        context["needs"] = action_needs_for_actor(self.request.user).prefetch_related("topics", "proposals")
        return context

    def post(self, request):
        form = self._form(request.POST)
        if form.is_valid():
            space = form.cleaned_data["space"]
            try:
                need = create_action_need(
                    actor=request.user,
                    owner_profile=None if space else request.user,
                    space=space,
                    title=form.cleaned_data["title"],
                    description=form.cleaned_data["description"],
                    match_kind=form.cleaned_data["match_kind"],
                    candidate_kind=form.cleaned_data["candidate_kind"],
                    visibility=form.cleaned_data["visibility"],
                    intake_policy=form.cleaned_data["intake_policy"],
                    target_count=form.cleaned_data["target_count"],
                    topics=form.cleaned_data["topics"],
                    activity=form.cleaned_data["activity"],
                    occurrence=form.cleaned_data["occurrence"],
                    opportunity=form.cleaned_data["opportunity"],
                )
            except (ValidationError, PermissionDenied) as exc:
                form.add_error(None, str(exc))
            else:
                messages.success(request, "Besoin créé. Makolo appliquera les règles de visibilité et de consentement choisies.")
                return redirect("social:need-detail", pk=need.pk)
        return self.render_to_response(self.get_context_data(form=form))


class ActionNeedDetailView(LoginRequiredMixin, TemplateView):
    template_name = "social/action_need_detail.html"
    login_url = "core:login"

    def _need(self):
        need = get_object_or_404(
            ActionNeed.objects.select_related("owner_profile", "space", "activity", "occurrence", "opportunity", "created_by").prefetch_related("topics"),
            pk=self.kwargs["pk"],
        )
        if not can_manage_action_need(self.request.user, need):
            raise PermissionDenied("Vous ne pouvez pas gérer ce besoin.")
        return need

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        need = self._need()
        context["need"] = need
        if need.status == ActionNeedStatus.OPEN:
            context["profile_candidates"] = search_profiles_for_need(need=need, limit=100)
            context["space_candidates"] = search_spaces_for_need(need=need, limit=100)
        else:
            context["profile_candidates"] = []
            context["space_candidates"] = []
        context["proposals"] = need.proposals.select_related("candidate_profile", "candidate_space", "initiated_by", "responded_by").order_by("-created_at")
        return context


class ActionNeedSolicitProfileView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, pk, profile_id):
        need = get_object_or_404(ActionNeed, pk=pk)
        recipient = get_object_or_404(User, pk=profile_id)
        try:
            create_action_proposal(
                actor=request.user,
                need=need,
                candidate_profile=recipient,
                direction=ActionProposalDirection.OWNER_TO_CANDIDATE,
                message=request.POST.get("message", ""),
            )
        except (ValidationError, PermissionDenied) as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Proposition envoyée dans Makolo.")
        return redirect("social:need-detail", pk=need.pk)


class ActionNeedSolicitSpaceView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, pk, space_id):
        need = get_object_or_404(ActionNeed, pk=pk)
        candidate_space = get_object_or_404(Organization, pk=space_id)
        try:
            create_action_proposal(
                actor=request.user,
                need=need,
                candidate_space=candidate_space,
                direction=ActionProposalDirection.OWNER_TO_CANDIDATE,
                message=request.POST.get("message", ""),
            )
        except (ValidationError, PermissionDenied) as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Proposition envoyée au Space dans Makolo.")
        return redirect("social:need-detail", pk=need.pk)


class ActionNeedProposeSelfView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, pk):
        need = get_object_or_404(ActionNeed, pk=pk)
        try:
            create_action_proposal(
                actor=request.user,
                need=need,
                candidate_profile=request.user,
                direction=ActionProposalDirection.CANDIDATE_TO_OWNER,
                message=request.POST.get("message", ""),
                client_reference=request.POST.get("client_reference") or None,
            )
        except (ValidationError, PermissionDenied) as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Votre proposition a été envoyée.")
        if need.activity_id:
            _, url = activity_destination(need.activity)
            return redirect(url)
        return redirect("social:network")


class ActionNeedCloseView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, pk):
        need = get_object_or_404(ActionNeed, pk=pk)
        close_action_need(actor=request.user, need=need)
        messages.success(request, "Besoin annulé. Aucune nouvelle proposition ne peut être envoyée.")
        return redirect("social:need-detail", pk=need.pk)


class ProfileSolicitationsView(LoginRequiredMixin, TemplateView):
    template_name = "social/profile_solicitations.html"
    login_url = "core:login"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        proposals = list(proposals_for_profile(self.request.user))
        for proposal in proposals:
            proposal.continuation_label = ""
            proposal.continuation_url = ""
            if proposal.status == ActionProposalStatus.ACCEPTED:
                if proposal.need.opportunity_id:
                    proposal.continuation_label = "Voir l’Opportunity"
                    proposal.continuation_url = reverse("opportunities:detail", kwargs={"pk": proposal.need.opportunity_id})
                elif proposal.need.activity_id:
                    proposal.continuation_label, proposal.continuation_url = activity_destination(proposal.need.activity)
        context["solicitations"] = proposals
        context["proposals"] = proposals
        return context


class ProfileSolicitationRespondView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, pk):
        proposal = get_object_or_404(ActionProposal, pk=pk)
        status = request.POST.get("status", "")
        try:
            if status not in {ActionProposalStatus.ACCEPTED, ActionProposalStatus.DECLINED}:
                raise ValidationError("Réponse invalide.")
            respond_to_action_proposal(
                actor=request.user,
                proposal=proposal,
                status=status,
                response_message=request.POST.get("response_message", ""),
            )
        except (ValidationError, PermissionDenied) as exc:
            if isinstance(exc, PermissionDenied):
                raise
            messages.error(request, str(exc))
        else:
            messages.success(request, "Votre réponse a été enregistrée sans créer de droit automatique.")
        return redirect("social:my-solicitations")


class ProfileSolicitationCancelView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, pk):
        proposal = get_object_or_404(ActionProposal.objects.select_related("need"), pk=pk)
        try:
            cancel_action_proposal(actor=request.user, proposal=proposal)
        except (ValidationError, PermissionDenied) as exc:
            if isinstance(exc, PermissionDenied):
                raise
            messages.error(request, str(exc))
        else:
            messages.success(request, "Proposition annulée.")
        return redirect("social:need-detail", pk=proposal.need_id)


# Compatibility class name used by the existing URL module/tests.
ActionNeedSolicitView = ActionNeedSolicitProfileView
