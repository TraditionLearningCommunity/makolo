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

from .action_stream import build_action_stream
from .bilateral_services import (
    can_manage_action_need,
    cancel_profile_solicitation,
    close_action_need,
    create_action_need,
    create_profile_solicitation,
    respond_to_profile_solicitation,
)
from .forms import ActionNeedForm
from .models import (
    ActionNeed,
    ActionNeedStatus,
    Contribution,
    ContributionKind,
    ContributionStatus,
    ProfileSolicitation,
    ProfileSolicitationStatus,
)
from .profile_search import action_needs_for_actor, search_profiles_for_need, solicitations_for_recipient
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
        context["needs"] = action_needs_for_actor(self.request.user).prefetch_related("topics", "solicitations")
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
                    open_to_kind=form.cleaned_data["open_to_kind"],
                    topics=form.cleaned_data["topics"],
                    activity=form.cleaned_data["activity"],
                    opportunity=form.cleaned_data["opportunity"],
                )
            except (ValidationError, PermissionDenied) as exc:
                form.add_error(None, str(exc))
            else:
                messages.success(request, "Besoin créé. La recherche n'utilisera que des signaux autorisés.")
                return redirect("social:need-detail", pk=need.pk)
        return self.render_to_response(self.get_context_data(form=form))


class ActionNeedDetailView(LoginRequiredMixin, TemplateView):
    template_name = "social/action_need_detail.html"
    login_url = "core:login"

    def _need(self):
        need = get_object_or_404(
            ActionNeed.objects.select_related("owner_profile", "space", "activity", "opportunity", "created_by").prefetch_related("topics"),
            pk=self.kwargs["pk"],
        )
        if not can_manage_action_need(self.request.user, need):
            raise PermissionDenied("Vous ne pouvez pas gérer ce besoin.")
        return need

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        need = self._need()
        context["need"] = need
        context["candidates"] = search_profiles_for_need(need=need, limit=100) if need.status == ActionNeedStatus.OPEN else []
        context["solicitations"] = need.solicitations.select_related("recipient_profile", "sent_by").order_by("-created_at")
        return context


class ActionNeedSolicitView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, pk, profile_id):
        need = get_object_or_404(ActionNeed, pk=pk)
        recipient = get_object_or_404(User, pk=profile_id)
        try:
            create_profile_solicitation(actor=request.user, need=need, recipient_profile=recipient, message=request.POST.get("message", ""))
        except ValidationError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Sollicitation envoyée dans Makolo.")
        return redirect("social:need-detail", pk=need.pk)


class ActionNeedCloseView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, pk):
        need = get_object_or_404(ActionNeed, pk=pk)
        close_action_need(actor=request.user, need=need)
        messages.success(request, "Besoin fermé. Aucune nouvelle sollicitation ne peut être envoyée.")
        return redirect("social:need-detail", pk=need.pk)


class ProfileSolicitationsView(LoginRequiredMixin, TemplateView):
    template_name = "social/profile_solicitations.html"
    login_url = "core:login"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        solicitations = list(solicitations_for_recipient(self.request.user))
        for solicitation in solicitations:
            solicitation.continuation_label = ""
            solicitation.continuation_url = ""
            if solicitation.status == ProfileSolicitationStatus.ACCEPTED:
                if solicitation.need.opportunity_id:
                    solicitation.continuation_label = "Voir l’Opportunity"
                    solicitation.continuation_url = reverse("opportunities:detail", kwargs={"pk": solicitation.need.opportunity_id})
                elif solicitation.need.activity_id:
                    solicitation.continuation_label, solicitation.continuation_url = activity_destination(solicitation.need.activity)
        context["solicitations"] = solicitations
        return context


class ProfileSolicitationRespondView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, pk):
        solicitation = get_object_or_404(ProfileSolicitation, pk=pk)
        status = request.POST.get("status", "")
        try:
            if status not in {ProfileSolicitationStatus.ACCEPTED, ProfileSolicitationStatus.DECLINED}:
                raise ValidationError("Réponse invalide.")
            respond_to_profile_solicitation(actor=request.user, solicitation=solicitation, status=status)
        except ValidationError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Votre réponse a été enregistrée sans créer de droit automatique.")
        return redirect("social:my-solicitations")


class ProfileSolicitationCancelView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, pk):
        solicitation = get_object_or_404(ProfileSolicitation.objects.select_related("need"), pk=pk)
        try:
            cancel_profile_solicitation(actor=request.user, solicitation=solicitation)
        except ValidationError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Sollicitation annulée.")
        return redirect("social:need-detail", pk=solicitation.need_id)
