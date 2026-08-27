from __future__ import annotations

import uuid

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Prefetch, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import FormView, TemplateView

from authorization.constants import PermissionCode, STANDARD_ACTIVITY_ROLE_CODES, STANDARD_SPACE_ROLE_CODES, SystemRoleCode
from authorization.models import AuthorityScope, Mandate, Role, RolePermission
from authorization.selectors import current_mandates
from authorization.services import can

from .console_views import SpaceConsoleMixin
from .models import Organization, Team, TeamMembership, TeamMembershipStatus
from .permissions import user_can_manage_organization_team
from .services import (
    add_existing_collaborator_to_team,
    add_or_update_member,
    archive_team,
    create_team,
    find_user_for_team,
    remove_member_from_team,
    rename_team,
)
from .team_forms import (
    MemberActivityResponsibilityForm,
    MemberSpaceResponsibilityForm,
    TeamExistingCollaboratorForm,
    TeamMemberCreateForm,
    TeamNameForm,
)
from .team_responsibilities import (
    grant_member_activity_responsibility,
    remove_member_from_space,
    revoke_member_activity_responsibility,
    update_member_space_responsibility,
)


def _role_catalog(*, scope_type, codes):
    permission_links = RolePermission.objects.select_related("permission").filter(permission__is_active=True).order_by("permission__name")
    return (
        Role.objects.filter(scope_type=scope_type, is_system=True, is_active=True, code__in=codes)
        .prefetch_related(Prefetch("role_permissions", queryset=permission_links, to_attr="console_permission_links"))
        .order_by("name", "code")
    )


class OrganizationMemberCreateView(View):
    """Add an existing Makolo Profile to the Space and its primary Team."""

    def _space(self, slug):
        return get_object_or_404(Organization, slug=slug)

    def get(self, request, slug):
        if not request.user.is_authenticated:
            raise PermissionDenied("Vous devez être connecté.")
        space = self._space(slug)
        if not user_can_manage_organization_team(request.user, space):
            raise PermissionDenied("Vous ne pouvez pas gérer cette équipe.")
        return render(
            request,
            "organizations/member_form.html",
            {"organization": space, "space": space, "form": TeamMemberCreateForm(actor=request.user, space=space)},
        )

    def post(self, request, slug):
        if not request.user.is_authenticated:
            raise PermissionDenied("Vous devez être connecté.")
        space = self._space(slug)
        if not user_can_manage_organization_team(request.user, space):
            raise PermissionDenied("Vous ne pouvez pas gérer cette équipe.")
        form = TeamMemberCreateForm(request.POST, actor=request.user, space=space)
        if form.is_valid():
            try:
                user = find_user_for_team(email=form.cleaned_data["email"])
                add_or_update_member(
                    organization=space,
                    actor=request.user,
                    user=user,
                    role=form.cleaned_data["role"],
                )
            except (ValidationError, PermissionDenied) as exc:
                form.add_error(None, "; ".join(getattr(exc, "messages", [str(exc)])))
            else:
                messages.success(request, "Collaborateur et responsabilité ajoutés à l’Espace.")
                return redirect("organizations:console-team", slug=space.slug)
        return render(
            request,
            "organizations/member_form.html",
            {"organization": space, "space": space, "form": form},
            status=400,
        )


class _SpaceTeamManagementMixin(SpaceConsoleMixin):
    module_key = "team"

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        if not self.space_console.can_manage_team:
            raise PermissionDenied("Vous ne pouvez pas gérer les équipes de cet Espace.")
        return response

    def get_team(self, *, active_only=False):
        queryset = Team.objects.filter(organization=self.space)
        if active_only:
            queryset = queryset.filter(is_active=True)
        return get_object_or_404(queryset, pk=self.kwargs["team_id"])


class SpaceTeamCreateView(_SpaceTeamManagementMixin, FormView):
    template_name = "organizations/console/team_form.html"
    form_class = TeamNameForm
    page_title = "Créer une équipe"

    def form_valid(self, form):
        try:
            create_team(organization=self.space, actor=self.request.user, name=form.cleaned_data["name"])
        except (ValidationError, PermissionDenied) as exc:
            form.add_error(None, "; ".join(getattr(exc, "messages", [str(exc)])))
            return self.form_invalid(form)
        messages.success(self.request, "Équipe créée. Aucune Permission n’a été accordée automatiquement.")
        return redirect("organizations:console-team", slug=self.space.slug)


class SpaceTeamRenameView(_SpaceTeamManagementMixin, FormView):
    template_name = "organizations/console/team_form.html"
    form_class = TeamNameForm
    page_title = "Renommer l’équipe"

    def get_initial(self):
        return {"name": self.get_team().name}

    def form_valid(self, form):
        try:
            rename_team(team=self.get_team(), actor=self.request.user, name=form.cleaned_data["name"])
        except (ValidationError, PermissionDenied) as exc:
            form.add_error(None, "; ".join(getattr(exc, "messages", [str(exc)])))
            return self.form_invalid(form)
        messages.success(self.request, "Équipe renommée sans modifier ses membres ni leurs responsabilités.")
        return redirect("organizations:console-team", slug=self.space.slug)


class SpaceTeamArchiveView(_SpaceTeamManagementMixin, View):
    def post(self, request, *args, **kwargs):
        try:
            archive_team(team=self.get_team(), actor=request.user)
        except (ValidationError, PermissionDenied) as exc:
            messages.error(request, "; ".join(getattr(exc, "messages", [str(exc)])))
        else:
            messages.success(request, "Équipe archivée. Son historique de Membership est conservé.")
        return redirect("organizations:console-team", slug=self.space.slug)


class SpaceTeamAddMemberView(_SpaceTeamManagementMixin, FormView):
    template_name = "organizations/console/team_member_form.html"
    form_class = TeamExistingCollaboratorForm
    page_title = "Ajouter à une équipe"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["team"] = self.get_team(active_only=True)
        return context

    def form_valid(self, form):
        team = self.get_team(active_only=True)
        try:
            user = find_user_for_team(email=form.cleaned_data["email"])
            add_existing_collaborator_to_team(team=team, actor=self.request.user, user=user)
        except (ValidationError, PermissionDenied) as exc:
            form.add_error(None, "; ".join(getattr(exc, "messages", [str(exc)])))
            return self.form_invalid(form)
        messages.success(self.request, f"Collaborateur ajouté à {team.name}. Ses Mandates n’ont pas été modifiés.")
        return redirect("organizations:console-team", slug=self.space.slug)


class SpaceTeamRemoveMemberView(_SpaceTeamManagementMixin, View):
    def post(self, request, *args, **kwargs):
        team = self.get_team()
        membership = get_object_or_404(
            TeamMembership.objects.select_related("team__organization", "user"),
            pk=kwargs["membership_id"],
            team=team,
        )
        try:
            remove_member_from_team(membership=membership, actor=request.user)
        except (ValidationError, PermissionDenied) as exc:
            messages.error(request, "; ".join(getattr(exc, "messages", [str(exc)])))
        else:
            messages.success(request, f"Collaborateur retiré de {team.name}. Ses autres équipes et Mandates sont inchangés.")
        return redirect("organizations:console-team", slug=self.space.slug)


class SpaceConsoleMemberResponsibilitiesView(SpaceConsoleMixin, TemplateView):
    template_name = "organizations/console/member_responsibilities.html"
    module_key = "team"
    page_title = "Responsabilités"

    def get_membership(self):
        return get_object_or_404(
            TeamMembership.objects.select_related("team__organization", "user"),
            pk=self.kwargs["membership_id"],
            team__organization=self.space,
            team__is_default=True,
        )

    def _responsibilities(self, membership):
        mandates = list(
            current_mandates()
            .filter(profile=membership.user)
            .filter(
                Q(scope_type=AuthorityScope.SPACE, space=self.space)
                | Q(scope_type=AuthorityScope.ACTIVITY, activity__space=self.space)
            )
            .select_related("role", "activity")
            .order_by("activity__title", "role__name", "pk")
        )
        standard_space = next(
            (
                mandate
                for mandate in mandates
                if mandate.scope_type == AuthorityScope.SPACE
                and mandate.role.is_system
                and mandate.role.code in STANDARD_SPACE_ROLE_CODES
            ),
            None,
        )
        custom_space = [
            mandate
            for mandate in mandates
            if mandate.scope_type == AuthorityScope.SPACE and not mandate.role.is_system
        ]
        activity = [mandate for mandate in mandates if mandate.scope_type == AuthorityScope.ACTIVITY]
        return standard_space, custom_space, activity

    def _context(self, *, space_form=None, activity_form=None):
        membership = self.get_membership()
        standard_space, custom_space, activity_mandates = self._responsibilities(membership)
        current_role_code = standard_space.role.code if standard_space else None
        can_manage_ownership = can(self.request.user, PermissionCode.SPACE_OWNERSHIP_MANAGE, self.space)
        current_is_owner = current_role_code == SystemRoleCode.SPACE_OWNER
        if space_form is None:
            space_form = MemberSpaceResponsibilityForm(
                actor=self.request.user,
                space=self.space,
                current_role_code=current_role_code,
                auto_id="id_space_%s",
            )
        if activity_form is None:
            activity_form = MemberActivityResponsibilityForm(
                space=self.space,
                auto_id="id_activity_%s",
            )
        context = super().get_context_data()
        context.update(
            {
                "membership": membership,
                "standard_space_mandate": standard_space,
                "custom_space_mandates": custom_space,
                "activity_mandates": activity_mandates,
                "space_form": space_form,
                "activity_form": activity_form,
                "can_manage_ownership": can_manage_ownership,
                "can_edit_space_role": membership.status == TeamMembershipStatus.ACTIVE and (not current_is_owner or can_manage_ownership),
                "space_role_catalog": _role_catalog(scope_type=AuthorityScope.SPACE, codes=STANDARD_SPACE_ROLE_CODES).exclude(code=SystemRoleCode.SPACE_OWNER) if not can_manage_ownership else _role_catalog(scope_type=AuthorityScope.SPACE, codes=STANDARD_SPACE_ROLE_CODES),
                "activity_role_catalog": _role_catalog(scope_type=AuthorityScope.ACTIVITY, codes=STANDARD_ACTIVITY_ROLE_CODES),
            }
        )
        context["console_page_title"] = f"Responsabilités de {membership.user.full_name or membership.user.username}"
        return context

    def get(self, request, *args, **kwargs):
        return self.render_to_response(self._context())

    def post(self, request, *args, **kwargs):
        membership = self.get_membership()
        if membership.status != TeamMembershipStatus.ACTIVE:
            raise PermissionDenied("Ce membre n'est plus actif dans l'équipe principale.")
        action = (request.POST.get("action") or "").strip()

        if action == "space-role":
            current_standard, _, _ = self._responsibilities(membership)
            current_role_code = current_standard.role.code if current_standard else None
            form = MemberSpaceResponsibilityForm(
                request.POST,
                actor=request.user,
                space=self.space,
                current_role_code=current_role_code,
                auto_id="id_space_%s",
            )
            if form.is_valid():
                try:
                    update_member_space_responsibility(
                        membership=membership,
                        actor=request.user,
                        role_code=form.cleaned_data["role"],
                    )
                except (PermissionDenied, ValidationError) as exc:
                    form.add_error(None, "; ".join(getattr(exc, "messages", [str(exc)])))
                else:
                    messages.success(request, "Responsabilité dans l'Espace mise à jour.")
                    return redirect("organizations:member-responsibilities", slug=self.space.slug, membership_id=membership.pk)
            return self.render_to_response(self._context(space_form=form), status=400)

        if action == "activity-add":
            form = MemberActivityResponsibilityForm(
                request.POST,
                space=self.space,
                auto_id="id_activity_%s",
            )
            if form.is_valid():
                try:
                    grant_member_activity_responsibility(
                        membership=membership,
                        actor=request.user,
                        activity=form.cleaned_data["activity"],
                        role_code=form.cleaned_data["role"],
                    )
                except (PermissionDenied, ValidationError) as exc:
                    form.add_error(None, "; ".join(getattr(exc, "messages", [str(exc)])))
                else:
                    messages.success(request, "Responsabilité sur l'activité ajoutée.")
                    return redirect("organizations:member-responsibilities", slug=self.space.slug, membership_id=membership.pk)
            return self.render_to_response(self._context(activity_form=form), status=400)

        if action == "activity-revoke":
            mandate_id = (request.POST.get("mandate_id") or "").strip()
            try:
                parsed_id = uuid.UUID(mandate_id)
            except (TypeError, ValueError, AttributeError):
                raise PermissionDenied("Responsabilité Activity invalide.")
            mandate = get_object_or_404(Mandate, pk=parsed_id)
            try:
                revoke_member_activity_responsibility(
                    membership=membership,
                    actor=request.user,
                    mandate=mandate,
                )
            except (PermissionDenied, ValidationError) as exc:
                messages.error(request, "; ".join(getattr(exc, "messages", [str(exc)])))
            else:
                messages.success(request, "Responsabilité sur l'activité retirée.")
            return redirect("organizations:member-responsibilities", slug=self.space.slug, membership_id=membership.pk)

        raise PermissionDenied("Action de responsabilité inconnue.")


class OrganizationMemberDeactivateView(SpaceConsoleMixin, View):
    module_key = "team"

    def post(self, request, *args, **kwargs):
        membership = get_object_or_404(
            TeamMembership.objects.select_related("team__organization", "user"),
            pk=kwargs["pk"],
            team__organization=self.space,
            team__is_default=True,
        )
        try:
            remove_member_from_space(membership=membership, actor=request.user)
        except (ValidationError, PermissionDenied) as exc:
            messages.error(request, "; ".join(getattr(exc, "messages", [str(exc)])))
        else:
            messages.success(request, "Collaborateur retiré de l’Espace ; ses TeamMemberships locales et responsabilités de cet Espace sont révoquées.")
        return redirect("organizations:console-team", slug=self.space.slug)