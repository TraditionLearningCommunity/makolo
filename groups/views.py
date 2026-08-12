from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views import View

from authorization.constants import PermissionCode
from organizations.models import Organization

from .forms import (
    AddMemberForm,
    GroupCreateForm,
    GroupImportForm,
    GroupInvitationForm,
    GroupResponsibilityForm,
    GroupUpdateForm,
    SnapshotForm,
    TransferOwnershipForm,
)
from .models import (
    Group,
    GroupInvitation,
    GroupInvitationStatus,
    GroupMembership,
    GroupMembershipStatus,
)
from .selectors import (
    direct_group_role_codes,
    get_group_for_profile,
    group_members_for_admin,
    groups_for_profile,
    pending_invitations_for_admin,
)
from .services import (
    _invitation_matches_profile,
    _token_digest,
    accept_invitation,
    add_member,
    archive_group,
    assign_group_responsibility,
    create_group,
    create_snapshot,
    has_group_permission,
    import_group_csv,
    invite_member,
    leave_group,
    reject_invitation,
    remove_member,
    require_group_permission,
    revoke_invitation,
    suspend_member,
    transfer_personal_group_ownership,
    update_group,
)


def _group_or_404(slug):
    try:
        return Group.objects.select_related("space", "owner_profile", "created_by").get(slug=slug)
    except Group.DoesNotExist as exc:
        raise Http404 from exc


def _validation_messages(exc):
    if hasattr(exc, "message_dict"):
        return [message for values in exc.message_dict.values() for message in values]
    return exc.messages


class GroupListView(LoginRequiredMixin, View):
    login_url = "core:login"

    def get(self, request):
        space = None
        space_id = request.GET.get("space")
        if space_id:
            try:
                space = Organization.objects.get(pk=space_id)
            except (Organization.DoesNotExist, ValueError) as exc:
                raise Http404 from exc
        return render(
            request,
            "groups/list.html",
            {"groups": groups_for_profile(request.user, space=space), "space": space},
        )


class GroupCreateView(LoginRequiredMixin, View):
    login_url = "core:login"

    def get(self, request):
        form = GroupCreateForm(actor=request.user, initial={"space": request.GET.get("space") or None})
        return render(request, "groups/create.html", {"form": form})

    def post(self, request):
        form = GroupCreateForm(request.POST, actor=request.user)
        if form.is_valid():
            try:
                group = create_group(actor=request.user, **form.cleaned_data)
            except (ValidationError, PermissionDenied) as exc:
                if isinstance(exc, PermissionDenied):
                    raise
                for message in _validation_messages(exc):
                    form.add_error(None, message)
            else:
                messages.success(request, "Groupe créé. Son administration passe par les Mandats, jamais par la simple appartenance.")
                return redirect("groups:detail", slug=group.slug)
        return render(request, "groups/create.html", {"form": form}, status=400)


class GroupDetailView(LoginRequiredMixin, View):
    login_url = "core:login"

    def get(self, request, slug):
        group = get_group_for_profile(request.user, slug=slug)
        can_manage = has_group_permission(request.user, PermissionCode.GROUP_MANAGE, group)
        can_members = has_group_permission(request.user, PermissionCode.GROUP_MEMBERS_VIEW, group)
        can_invite = has_group_permission(request.user, PermissionCode.GROUP_INVITATIONS_MANAGE, group)
        can_snapshot = has_group_permission(request.user, PermissionCode.GROUP_SNAPSHOTS_CREATE, group)
        can_ownership = has_group_permission(request.user, PermissionCode.GROUP_OWNERSHIP_MANAGE, group)
        active_member_count = group.memberships.filter(status=GroupMembershipStatus.ACTIVE).count()
        membership = group.memberships.filter(profile=request.user).first()
        return render(
            request,
            "groups/detail.html",
            {
                "group": group,
                "active_member_count": active_member_count,
                "membership": membership,
                "direct_roles": direct_group_role_codes(request.user, group),
                "can_manage": can_manage,
                "can_members": can_members,
                "can_invite": can_invite,
                "can_snapshot": can_snapshot,
                "can_ownership": can_ownership,
                "snapshots": group.snapshots.all()[:10] if can_snapshot else [],
            },
        )


class GroupEditView(LoginRequiredMixin, View):
    login_url = "core:login"

    def get(self, request, slug):
        group = _group_or_404(slug)
        require_group_permission(request.user, PermissionCode.GROUP_MANAGE, group)
        return render(request, "groups/edit.html", {"group": group, "form": GroupUpdateForm(group=group)})

    def post(self, request, slug):
        group = _group_or_404(slug)
        require_group_permission(request.user, PermissionCode.GROUP_MANAGE, group)
        form = GroupUpdateForm(request.POST, group=group)
        if form.is_valid():
            try:
                group = update_group(actor=request.user, group=group, **form.cleaned_data)
            except ValidationError as exc:
                for message in _validation_messages(exc):
                    form.add_error(None, message)
            else:
                messages.success(request, "Groupe mis à jour.")
                return redirect("groups:detail", slug=group.slug)
        return render(request, "groups/edit.html", {"group": group, "form": form}, status=400)


class GroupMembersView(LoginRequiredMixin, View):
    login_url = "core:login"

    def get(self, request, slug):
        group = _group_or_404(slug)
        members = group_members_for_admin(request.user, group)
        invitations = []
        if has_group_permission(request.user, PermissionCode.GROUP_INVITATIONS_MANAGE, group):
            invitations = pending_invitations_for_admin(request.user, group)
        return render(
            request,
            "groups/members.html",
            {
                "group": group,
                "members": members,
                "invitations": invitations,
                "can_manage_members": has_group_permission(request.user, PermissionCode.GROUP_MEMBERS_MANAGE, group),
                "can_invite": has_group_permission(request.user, PermissionCode.GROUP_INVITATIONS_MANAGE, group),
                "can_ownership": has_group_permission(request.user, PermissionCode.GROUP_OWNERSHIP_MANAGE, group),
            },
        )


class GroupAddMemberView(LoginRequiredMixin, View):
    login_url = "core:login"

    def get(self, request, slug):
        group = _group_or_404(slug)
        require_group_permission(request.user, PermissionCode.GROUP_MEMBERS_MANAGE, group)
        return render(request, "groups/add_member.html", {"group": group, "form": AddMemberForm()})

    def post(self, request, slug):
        group = _group_or_404(slug)
        require_group_permission(request.user, PermissionCode.GROUP_MEMBERS_MANAGE, group)
        form = AddMemberForm(request.POST)
        if form.is_valid():
            try:
                _, created = add_member(
                    actor=request.user,
                    group=group,
                    profile=form.profile,
                    external_reference=form.cleaned_data["external_reference"],
                )
            except ValidationError as exc:
                for message in _validation_messages(exc):
                    form.add_error(None, message)
            else:
                messages.success(request, "Membre ajouté." if created else "Ce Profil était déjà membre actif.")
                return redirect("groups:members", slug=group.slug)
        return render(request, "groups/add_member.html", {"group": group, "form": form}, status=400)


class GroupMemberStateView(LoginRequiredMixin, View):
    login_url = "core:login"
    action = None

    def post(self, request, slug, profile_id):
        group = _group_or_404(slug)
        require_group_permission(request.user, PermissionCode.GROUP_MEMBERS_MANAGE, group)
        try:
            profile = group.memberships.select_related("profile").get(profile_id=profile_id).profile
        except GroupMembership.DoesNotExist as exc:
            raise Http404 from exc
        if self.action == "suspend":
            suspend_member(actor=request.user, group=group, profile=profile)
            messages.success(request, "Membre suspendu.")
        elif self.action == "remove":
            remove_member(actor=request.user, group=group, profile=profile)
            messages.success(request, "Membre retiré du Groupe.")
        return redirect("groups:members", slug=group.slug)


class GroupSuspendMemberView(GroupMemberStateView):
    action = "suspend"


class GroupRemoveMemberView(GroupMemberStateView):
    action = "remove"


class GroupLeaveView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, slug):
        group = get_group_for_profile(request.user, slug=slug)
        leave_group(profile=request.user, group=group)
        messages.success(request, "Vous avez quitté le Groupe.")
        return redirect("groups:list")


class GroupInviteView(LoginRequiredMixin, View):
    login_url = "core:login"

    def get(self, request, slug):
        group = _group_or_404(slug)
        require_group_permission(request.user, PermissionCode.GROUP_INVITATIONS_MANAGE, group)
        return render(request, "groups/invite.html", {"group": group, "form": GroupInvitationForm()})

    def post(self, request, slug):
        group = _group_or_404(slug)
        require_group_permission(request.user, PermissionCode.GROUP_INVITATIONS_MANAGE, group)
        form = GroupInvitationForm(request.POST)
        if form.is_valid():
            try:
                invitation, token = invite_member(actor=request.user, group=group, **form.cleaned_data)
            except ValidationError as exc:
                for message in _validation_messages(exc):
                    form.add_error(None, message)
            else:
                invitation_path = reverse("groups:invitation", kwargs={"token": token})
                return render(
                    request,
                    "groups/invite.html",
                    {
                        "group": group,
                        "form": GroupInvitationForm(),
                        "invitation": invitation,
                        "invitation_path": invitation_path,
                    },
                )
        return render(request, "groups/invite.html", {"group": group, "form": form}, status=400)


class GroupRevokeInvitationView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, slug, invitation_id):
        group = _group_or_404(slug)
        require_group_permission(request.user, PermissionCode.GROUP_INVITATIONS_MANAGE, group)
        try:
            invitation = group.invitations.get(pk=invitation_id)
        except (GroupInvitation.DoesNotExist, ValueError) as exc:
            raise Http404 from exc
        revoke_invitation(actor=request.user, invitation=invitation)
        messages.success(request, "Invitation révoquée.")
        return redirect("groups:members", slug=group.slug)


class GroupImportView(LoginRequiredMixin, View):
    login_url = "core:login"

    def get(self, request, slug):
        group = _group_or_404(slug)
        require_group_permission(request.user, PermissionCode.GROUP_MEMBERS_MANAGE, group)
        require_group_permission(request.user, PermissionCode.GROUP_INVITATIONS_MANAGE, group)
        return render(request, "groups/import.html", {"group": group, "form": GroupImportForm()})

    def post(self, request, slug):
        group = _group_or_404(slug)
        require_group_permission(request.user, PermissionCode.GROUP_MEMBERS_MANAGE, group)
        require_group_permission(request.user, PermissionCode.GROUP_INVITATIONS_MANAGE, group)
        form = GroupImportForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                result = import_group_csv(actor=request.user, group=group, upload=form.cleaned_data["csv_file"])
            except ValidationError as exc:
                for message in _validation_messages(exc):
                    form.add_error(None, message)
            else:
                return render(
                    request,
                    "groups/import.html",
                    {"group": group, "form": GroupImportForm(), "result": result},
                )
        return render(request, "groups/import.html", {"group": group, "form": form}, status=400)


class GroupSnapshotCreateView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, slug):
        group = _group_or_404(slug)
        require_group_permission(request.user, PermissionCode.GROUP_SNAPSHOTS_CREATE, group)
        form = SnapshotForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Le nom du snapshot est invalide.")
            return redirect("groups:detail", slug=group.slug)
        snapshot = create_snapshot(actor=request.user, group=group, name=form.cleaned_data["name"])
        messages.success(request, f"Snapshot créé avec {snapshot.member_count} membre(s) actif(s).")
        return redirect("groups:detail", slug=group.slug)


class GroupArchiveView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, slug):
        group = _group_or_404(slug)
        archive_group(actor=request.user, group=group)
        messages.success(request, "Groupe archivé. L'historique et les snapshots sont conservés.")
        return redirect("groups:detail", slug=group.slug)


class GroupTransferOwnershipView(LoginRequiredMixin, View):
    login_url = "core:login"

    def get(self, request, slug):
        group = _group_or_404(slug)
        require_group_permission(request.user, PermissionCode.GROUP_OWNERSHIP_MANAGE, group)
        if not group.owner_profile_id:
            raise PermissionDenied("Un Groupe d'Espace n'a pas de propriétaire Profil à transférer.")
        return render(request, "groups/transfer.html", {"group": group, "form": TransferOwnershipForm()})

    def post(self, request, slug):
        group = _group_or_404(slug)
        require_group_permission(request.user, PermissionCode.GROUP_OWNERSHIP_MANAGE, group)
        form = TransferOwnershipForm(request.POST)
        if form.is_valid():
            try:
                transfer_personal_group_ownership(actor=request.user, group=group, new_owner=form.new_owner)
            except ValidationError as exc:
                for message in _validation_messages(exc):
                    form.add_error(None, message)
            else:
                messages.success(request, "Propriété du Groupe transférée avec son Mandat propriétaire.")
                return redirect("groups:detail", slug=group.slug)
        return render(request, "groups/transfer.html", {"group": group, "form": form}, status=400)


class GroupResponsibilityView(LoginRequiredMixin, View):
    login_url = "core:login"

    def get(self, request, slug):
        group = _group_or_404(slug)
        require_group_permission(request.user, PermissionCode.GROUP_OWNERSHIP_MANAGE, group)
        return render(request, "groups/responsibility.html", {"group": group, "form": GroupResponsibilityForm()})

    def post(self, request, slug):
        group = _group_or_404(slug)
        require_group_permission(request.user, PermissionCode.GROUP_OWNERSHIP_MANAGE, group)
        form = GroupResponsibilityForm(request.POST)
        if form.is_valid():
            assign_group_responsibility(
                actor=request.user,
                group=group,
                profile=form.profile,
                role_code=form.cleaned_data["role_code"],
            )
            messages.success(request, "Responsabilité Groupe mise à jour par Mandat explicite.")
            return redirect("groups:members", slug=group.slug)
        return render(request, "groups/responsibility.html", {"group": group, "form": form}, status=400)


class GroupInvitationClaimView(View):
    def _invitation_for_user(self, request, token):
        digest = _token_digest(token)
        invitation = GroupInvitation.objects.select_related("group").filter(
            token_digest=digest,
            status=GroupInvitationStatus.PENDING,
        ).first()
        if not invitation:
            raise ValidationError("Cette invitation est invalide ou a déjà été utilisée.")
        if invitation.expires_at <= timezone.now():
            raise ValidationError("Cette invitation a expiré.")
        if not _invitation_matches_profile(invitation, request.user):
            raise PermissionDenied("Cette invitation ne correspond pas au Profil connecté.")
        return invitation

    def get(self, request, token):
        if not request.user.is_authenticated:
            next_path = reverse("groups:invitation", kwargs={"token": token})
            login_url = f"{reverse('core:login')}?{urlencode({'next': next_path})}"
            register_url = f"{reverse('account:register')}?{urlencode({'next': next_path})}"
            return render(
                request,
                "groups/invitation_claim.html",
                {"login_url": login_url, "register_url": register_url},
            )
        try:
            invitation = self._invitation_for_user(request, token)
        except ValidationError as exc:
            return render(
                request,
                "groups/invitation_claim.html",
                {"invalid_message": " ".join(exc.messages)},
                status=400,
            )
        return render(request, "groups/invitation_claim.html", {"invitation": invitation, "token": token})

    def post(self, request, token):
        if not request.user.is_authenticated:
            next_path = reverse("groups:invitation", kwargs={"token": token})
            return redirect(f"{reverse('core:login')}?{urlencode({'next': next_path})}")
        action = request.POST.get("action", "accept")
        try:
            if action == "reject":
                reject_invitation(profile=request.user, token=token)
                messages.success(request, "Invitation refusée.")
                return redirect("groups:list")
            invitation, _ = accept_invitation(profile=request.user, token=token)
        except ValidationError as exc:
            return render(
                request,
                "groups/invitation_claim.html",
                {"invalid_message": " ".join(exc.messages)},
                status=400,
            )
        messages.success(request, "Invitation acceptée. Vous êtes maintenant membre du Groupe.")
        return redirect("groups:detail", slug=invitation.group.slug)
