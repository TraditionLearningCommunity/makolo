from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views import View
from django.views.generic import TemplateView

from activities.models import Activity
from groups.models import Group
from notifications.models import NotificationCategory, NotificationKind
from notifications.services import create_notification

from .action_stream import build_action_stream
from .models import Contribution, ContributionKind, ContributionStatus
from .selectors import group_contributions
from .services import create_contribution, moderate_contribution, share_activity_to_group


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
