from django import forms

from activities.models import Activity
from authorization.constants import PermissionCode, STANDARD_ACTIVITY_ROLE_CODES, STANDARD_SPACE_ROLE_CODES, SystemRoleCode
from authorization.models import AuthorityScope, Role
from authorization.services import can

from .forms import INPUT_CLASS, OrganizationMemberForm


class TeamMemberCreateForm(OrganizationMemberForm):
    """Existing add-member form with ownership choices filtered for the actor."""

    def __init__(self, *args, actor, space, **kwargs):
        super().__init__(*args, **kwargs)
        if not can(actor, PermissionCode.SPACE_OWNERSHIP_MANAGE, space):
            self.fields["role"].choices = [
                choice for choice in self.fields["role"].choices if choice[0] != SystemRoleCode.SPACE_OWNER
            ]


class MemberSpaceResponsibilityForm(forms.Form):
    role = forms.ChoiceField(
        label="Responsabilité dans l'Espace",
        help_text="Choisissez la responsabilité générale de cette personne dans cet Espace.",
    )

    def __init__(self, *args, actor, space, current_role_code=None, **kwargs):
        super().__init__(*args, **kwargs)
        can_manage_ownership = can(actor, PermissionCode.SPACE_OWNERSHIP_MANAGE, space)
        roles = list(
            Role.objects.filter(
                scope_type=AuthorityScope.SPACE,
                is_system=True,
                is_active=True,
                code__in=STANDARD_SPACE_ROLE_CODES,
            ).order_by("name", "code")
        )
        choices = []
        for role in roles:
            if role.code == SystemRoleCode.SPACE_OWNER and not can_manage_ownership and current_role_code != role.code:
                continue
            choices.append((role.code, role.name))
        self.fields["role"].choices = choices
        self.fields["role"].widget.attrs["class"] = INPUT_CLASS
        if current_role_code:
            self.fields["role"].initial = current_role_code
        if current_role_code == SystemRoleCode.SPACE_OWNER and not can_manage_ownership:
            self.fields["role"].disabled = True


class MemberActivityResponsibilityForm(forms.Form):
    activity = forms.ModelChoiceField(
        queryset=Activity.objects.none(),
        label="Activité",
        help_text="Seules les activités de cet Espace peuvent être ciblées.",
    )
    role = forms.ChoiceField(
        label="Responsabilité",
        help_text="Cette responsabilité sera limitée à l'activité choisie.",
    )

    def __init__(self, *args, space, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["activity"].queryset = Activity.objects.filter(space=space).order_by("title", "pk")
        roles = Role.objects.filter(
            scope_type=AuthorityScope.ACTIVITY,
            is_system=True,
            is_active=True,
            code__in=STANDARD_ACTIVITY_ROLE_CODES,
        ).order_by("name", "code")
        self.fields["role"].choices = [(role.code, role.name) for role in roles]
        for field in self.fields.values():
            field.widget.attrs["class"] = INPUT_CLASS
