from __future__ import annotations

import uuid

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Prefetch, Q
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import TemplateView

from authorization.constants import PermissionCode, STANDARD_ACTIVITY_ROLE_CODES, STANDARD_SPACE_ROLE_CODES, SystemRoleCode
from authorization.models import AuthorityScope, Mandate, Role, RolePermission
from authorization.selectors import current_mandates
from authorization.services import can

from .console_views import SpaceConsoleMixin
from .models import TeamMembership, TeamMembershipStatus
from .team_forms import MemberActivityResponsibilityForm, MemberSpaceResponsibilityForm
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


class SpaceConsoleMemberResponsibilitiesView(SpaceConsoleMixin, TemplateView):
    template_name = "organizations/console/member_responsibilities.html"
    module_key = "team"
    page_title = "Responsabilités"

    def get_membership(self):
        return get_object_or_404(
            TeamMembership.objects.select_related("team__organization", "user"),
            pk=self.kwargs["membership_id"],
            team__organization=self.space,
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
            )
        if activity_form is None:
            activity_form = MemberActivityResponsibilityForm(space=self.space)
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
            raise PermissionDenied("Ce membre n'est plus actif dans l'équipe.")
        action = (request.POST.get("action") or "").strip()

        if action == "space-role":
            current_standard, _, _ = self._responsibilities(membership)
            current_role_code = current_standard.role.code if current_standard else None
            form = MemberSpaceResponsibilityForm(
                request.POST,
                actor=request.user,
                space=self.space,
                current_role_code=current_role_code,
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
            form = MemberActivityResponsibilityForm(request.POST, space=self.space)
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
        )
        try:
            remove_member_from_space(membership=membership, actor=request.user)
        except (ValidationError, PermissionDenied) as exc:
            messages.error(request, "; ".join(getattr(exc, "messages", [str(exc)])))
        else:
            messages.success(request, "Membre retiré de l'équipe et responsabilités de cet Espace révoquées.")
        return redirect("organizations:console-team", slug=self.space.slug)
