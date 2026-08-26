from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import redirect, render
from django.views import View

from activities.models import Activity
from activities.selectors import manageable_activities
from authorization.constants import PermissionCode

from .community_forms import ActivityEligibilityRequestForm, CommunityGroupForm, JoinRequestForm
from .community_group_services import create_community_group, update_community_group
from .community_selectors import (
    approved_activities_for_group_viewer,
    community_group_or_none,
    discoverable_groups,
    pending_activity_eligibilities_for_admin,
    pending_join_requests_for_admin,
    relationship_for_profile,
)
from .community_services import (
    approve_join_request,
    cancel_join_request,
    decide_activity_group_eligibility,
    group_owner_label,
    join_group,
    reject_join_request,
    request_activity_group_eligibility,
    request_to_join,
    revoke_activity_group_eligibility,
)
from .models import (
    ActivityGroupEligibility,
    Group,
    GroupJoinRequest,
    GroupMembershipPolicy,
    GroupMembershipStatus,
)
from .selectors import (
    direct_group_role_codes,
    group_members_for_admin,
    groups_for_profile,
    pending_invitations_for_admin,
)
from .services import has_group_permission


def _messages_for_validation(exc):
    if hasattr(exc, "message_dict"):
        return [message for values in exc.message_dict.values() for message in values]
    return getattr(exc, "messages", [str(exc)])


def _group_or_404_for_profile(profile, slug):
    group = community_group_or_none(profile=profile, slug=slug)
    if not group:
        raise Http404
    return group


class CommunityGroupListView(LoginRequiredMixin, View):
    login_url = "core:login"

    def get(self, request):
        space_id = request.GET.get("space")
        groups = groups_for_profile(request.user)
        if space_id:
            groups = groups.filter(space_id=space_id)
        invitations = request.user.collective_group_invitations.filter(status="pending")[:10]
        pending_requests = request.user.group_join_requests.filter(status="pending").select_related("group")[:10]
        return render(
            request,
            "groups/list.html",
            {
                "groups": groups,
                "invitations": invitations,
                "pending_requests": pending_requests,
            },
        )


class GroupExploreView(LoginRequiredMixin, View):
    login_url = "core:login"

    def get(self, request):
        query = (request.GET.get("q") or "").strip()
        paginator = Paginator(discoverable_groups(profile=request.user, query=query), 24)
        page = paginator.get_page(request.GET.get("page"))
        cards = [
            {"group": group, "owner_label": group_owner_label(group)}
            for group in page.object_list
        ]
        return render(
            request,
            "groups/explore.html",
            {"page_obj": page, "cards": cards, "query": query},
        )


class CommunityGroupCreateView(LoginRequiredMixin, View):
    login_url = "core:login"

    def get(self, request):
        form = CommunityGroupForm(
            actor=request.user,
            initial={"space": request.GET.get("space") or None},
        )
        return render(request, "groups/create.html", {"form": form})

    def post(self, request):
        form = CommunityGroupForm(request.POST, actor=request.user)
        if form.is_valid():
            try:
                group = create_community_group(actor=request.user, **form.cleaned_data)
            except PermissionDenied:
                raise
            except ValidationError as exc:
                for message in _messages_for_validation(exc):
                    form.add_error(None, message)
            else:
                messages.success(
                    request,
                    "Groupe créé. L'appartenance reste distincte des responsabilités administratives.",
                )
                return redirect("groups:detail", slug=group.slug)
        return render(request, "groups/create.html", {"form": form}, status=400)


class CommunityGroupEditView(LoginRequiredMixin, View):
    login_url = "core:login"

    def get(self, request, slug):
        group = _group_or_404_for_profile(request.user, slug)
        if not has_group_permission(request.user, PermissionCode.GROUP_MANAGE, group):
            raise PermissionDenied("Vous ne pouvez pas modifier ce Groupe.")
        return render(
            request,
            "groups/edit.html",
            {"group": group, "form": CommunityGroupForm(actor=request.user, group=group)},
        )

    def post(self, request, slug):
        group = _group_or_404_for_profile(request.user, slug)
        if not has_group_permission(request.user, PermissionCode.GROUP_MANAGE, group):
            raise PermissionDenied("Vous ne pouvez pas modifier ce Groupe.")
        form = CommunityGroupForm(request.POST, actor=request.user, group=group)
        if form.is_valid():
            cleaned = dict(form.cleaned_data)
            cleaned.pop("space", None)
            try:
                group = update_community_group(
                    actor=request.user,
                    group=group,
                    **cleaned,
                )
            except ValidationError as exc:
                for message in _messages_for_validation(exc):
                    form.add_error(None, message)
            else:
                messages.success(request, "Groupe mis à jour.")
                return redirect("groups:detail", slug=group.slug)
        return render(
            request,
            "groups/edit.html",
            {"group": group, "form": form},
            status=400,
        )


class CommunityGroupDetailView(LoginRequiredMixin, View):
    login_url = "core:login"

    def get(self, request, slug):
        group = _group_or_404_for_profile(request.user, slug)
        membership, join_request, invitation = relationship_for_profile(
            profile=request.user,
            group=group,
        )
        can_manage = has_group_permission(request.user, PermissionCode.GROUP_MANAGE, group)
        can_members = has_group_permission(
            request.user,
            PermissionCode.GROUP_MEMBERS_VIEW,
            group,
        )
        can_invite = has_group_permission(
            request.user,
            PermissionCode.GROUP_INVITATIONS_MANAGE,
            group,
        )
        can_snapshot = has_group_permission(
            request.user,
            PermissionCode.GROUP_SNAPSHOTS_CREATE,
            group,
        )
        active_member_count = group.memberships.filter(
            status=GroupMembershipStatus.ACTIVE
        ).count()
        manageable = manageable_activities(request.user).order_by("title", "id")[:100]
        return render(
            request,
            "groups/detail.html",
            {
                "group": group,
                "owner_label": group_owner_label(group),
                "active_member_count": active_member_count,
                "membership": membership,
                "join_request": join_request,
                "invitation": invitation,
                "direct_roles": direct_group_role_codes(request.user, group),
                "can_manage": can_manage,
                "can_members": can_members,
                "can_invite": can_invite,
                "can_snapshot": can_snapshot,
                "can_ownership": has_group_permission(
                    request.user,
                    PermissionCode.GROUP_OWNERSHIP_MANAGE,
                    group,
                ),
                "snapshots": group.snapshots.all()[:10] if can_snapshot else [],
                "related_activities": approved_activities_for_group_viewer(
                    profile=request.user,
                    group=group,
                ),
                "pending_activity_eligibilities": pending_activity_eligibilities_for_admin(
                    profile=request.user,
                    group=group,
                ),
                "manageable_activities": manageable,
                "join_form": JoinRequestForm(),
                "membership_policy_open": GroupMembershipPolicy.OPEN,
                "membership_policy_request": GroupMembershipPolicy.REQUEST,
            },
        )


class GroupJoinView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, slug):
        group = _group_or_404_for_profile(request.user, slug)
        try:
            _, created = join_group(profile=request.user, group=group)
        except (ValidationError, PermissionDenied) as exc:
            messages.error(request, str(exc))
        else:
            messages.success(
                request,
                "Vous avez rejoint le Groupe." if created else "Vous êtes déjà membre de ce Groupe.",
            )
        return redirect("groups:detail", slug=group.slug)


class GroupJoinRequestCreateView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, slug):
        group = _group_or_404_for_profile(request.user, slug)
        form = JoinRequestForm(request.POST)
        if not form.is_valid():
            messages.error(request, "La demande d'adhésion est invalide.")
            return redirect("groups:detail", slug=group.slug)
        try:
            _, created = request_to_join(
                profile=request.user,
                group=group,
                message=form.cleaned_data["message"],
            )
        except (ValidationError, PermissionDenied) as exc:
            messages.error(request, str(exc))
        else:
            messages.success(
                request,
                "Demande envoyée." if created else "Votre demande est déjà en attente.",
            )
        return redirect("groups:detail", slug=group.slug)


class GroupJoinRequestCancelView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, request_id):
        try:
            join_request = GroupJoinRequest.objects.select_related("group").get(pk=request_id)
        except (GroupJoinRequest.DoesNotExist, ValueError) as exc:
            raise Http404 from exc
        try:
            cancel_join_request(profile=request.user, request=join_request)
        except PermissionDenied:
            raise Http404
        except ValidationError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Demande annulée.")
        return redirect("groups:detail", slug=join_request.group.slug)


class CommunityGroupMembersView(LoginRequiredMixin, View):
    login_url = "core:login"

    def get(self, request, slug):
        try:
            group = Group.objects.select_related("space", "owner_profile").get(slug=slug)
        except Group.DoesNotExist as exc:
            raise Http404 from exc
        members = group_members_for_admin(request.user, group)
        can_manage_members = has_group_permission(
            request.user,
            PermissionCode.GROUP_MEMBERS_MANAGE,
            group,
        )
        invitations = []
        if has_group_permission(
            request.user,
            PermissionCode.GROUP_INVITATIONS_MANAGE,
            group,
        ):
            invitations = pending_invitations_for_admin(request.user, group)
        join_requests = (
            pending_join_requests_for_admin(profile=request.user, group=group)
            if can_manage_members
            else []
        )
        return render(
            request,
            "groups/members.html",
            {
                "group": group,
                "members": members,
                "invitations": invitations,
                "join_requests": join_requests,
                "can_manage_members": can_manage_members,
                "can_invite": has_group_permission(
                    request.user,
                    PermissionCode.GROUP_INVITATIONS_MANAGE,
                    group,
                ),
                "can_ownership": has_group_permission(
                    request.user,
                    PermissionCode.GROUP_OWNERSHIP_MANAGE,
                    group,
                ),
            },
        )


class GroupJoinRequestDecisionView(LoginRequiredMixin, View):
    login_url = "core:login"
    approve = False

    def post(self, request, slug, request_id):
        try:
            join_request = GroupJoinRequest.objects.select_related("group").get(
                pk=request_id,
                group__slug=slug,
            )
        except (GroupJoinRequest.DoesNotExist, ValueError) as exc:
            raise Http404 from exc
        if self.approve:
            approve_join_request(actor=request.user, request=join_request)
            messages.success(request, "Demande approuvée. Le membre est maintenant actif.")
        else:
            reject_join_request(actor=request.user, request=join_request)
            messages.success(request, "Demande refusée.")
        return redirect("groups:members", slug=slug)


class GroupJoinRequestApproveView(GroupJoinRequestDecisionView):
    approve = True


class GroupJoinRequestRejectView(GroupJoinRequestDecisionView):
    approve = False


class ActivityEligibilityRequestView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, slug):
        group = _group_or_404_for_profile(request.user, slug)
        form = ActivityEligibilityRequestForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Activity invalide.")
            return redirect("groups:detail", slug=group.slug)
        try:
            activity = Activity.objects.get(pk=form.cleaned_data["activity_id"])
        except Activity.DoesNotExist as exc:
            raise Http404 from exc
        try:
            relation, _ = request_activity_group_eligibility(
                actor=request.user,
                activity=activity,
                group=group,
            )
        except (PermissionDenied, ValidationError) as exc:
            messages.error(request, str(exc))
        else:
            if relation.status == "approved":
                messages.success(request, "Ce Groupe est maintenant autorisé pour l'Activity.")
            else:
                messages.success(request, "Demande d'utilisation envoyée au responsable du Groupe.")
        return redirect("groups:detail", slug=group.slug)


class ActivityEligibilityReviewView(LoginRequiredMixin, View):
    login_url = "core:login"

    def get(self, request, eligibility_id):
        try:
            eligibility = ActivityGroupEligibility.objects.select_related(
                "group",
                "activity",
                "requested_by",
            ).get(pk=eligibility_id)
        except (ActivityGroupEligibility.DoesNotExist, ValueError) as exc:
            raise Http404 from exc
        if not has_group_permission(
            request.user,
            PermissionCode.GROUP_MANAGE,
            eligibility.group,
        ):
            raise Http404
        return render(
            request,
            "groups/activity_eligibility_review.html",
            {"eligibility": eligibility},
        )


class ActivityEligibilityDecisionView(LoginRequiredMixin, View):
    login_url = "core:login"
    approve = False

    def post(self, request, eligibility_id):
        try:
            eligibility = ActivityGroupEligibility.objects.select_related("group").get(
                pk=eligibility_id
            )
        except (ActivityGroupEligibility.DoesNotExist, ValueError) as exc:
            raise Http404 from exc
        decide_activity_group_eligibility(
            actor=request.user,
            eligibility=eligibility,
            approve=self.approve,
        )
        messages.success(
            request,
            "Utilisation autorisée." if self.approve else "Utilisation refusée.",
        )
        return redirect("groups:detail", slug=eligibility.group.slug)


class ActivityEligibilityApproveView(ActivityEligibilityDecisionView):
    approve = True


class ActivityEligibilityRejectView(ActivityEligibilityDecisionView):
    approve = False


class ActivityEligibilityRevokeView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, eligibility_id):
        try:
            eligibility = ActivityGroupEligibility.objects.select_related("group").get(
                pk=eligibility_id
            )
        except (ActivityGroupEligibility.DoesNotExist, ValueError) as exc:
            raise Http404 from exc
        revoke_activity_group_eligibility(actor=request.user, eligibility=eligibility)
        messages.success(request, "Utilisation du Groupe révoquée.")
        return redirect("groups:detail", slug=eligibility.group.slug)
