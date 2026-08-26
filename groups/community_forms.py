from django import forms

from authorization.constants import PermissionCode
from authorization.services import space_ids_with_permission
from organizations.models import Organization

from .models import GroupDiscoverability, GroupMembershipPolicy


INPUT_CLASS = "w-full rounded-xl border px-3 py-2"


class CommunityGroupForm(forms.Form):
    name = forms.CharField(max_length=180, label="Nom")
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 4}),
        label="Description",
    )
    space = forms.ModelChoiceField(
        queryset=Organization.objects.none(),
        required=False,
        label="Créer pour",
        empty_label="Moi-même",
    )
    discoverability = forms.ChoiceField(
        choices=GroupDiscoverability.choices,
        initial=GroupDiscoverability.HIDDEN,
        label="Qui peut trouver ce Groupe ?",
    )
    membership_policy = forms.ChoiceField(
        choices=GroupMembershipPolicy.choices,
        initial=GroupMembershipPolicy.INVITE_ONLY,
        label="Qui peut rejoindre ?",
    )

    def __init__(self, *args, actor=None, group=None, **kwargs):
        if group and "initial" not in kwargs:
            kwargs["initial"] = {
                "name": group.name,
                "description": group.description,
                "space": group.space_id,
                "discoverability": group.discoverability,
                "membership_policy": group.membership_policy,
            }
        super().__init__(*args, **kwargs)
        self.group = group
        ids = space_ids_with_permission(actor, PermissionCode.SPACE_GROUPS_MANAGE) if actor else []
        queryset = Organization.objects.all() if ids is None else Organization.objects.filter(pk__in=ids)
        self.fields["space"].queryset = queryset.order_by("name")
        if group:
            self.fields["space"].disabled = True
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", INPUT_CLASS)

    def clean(self):
        cleaned = super().clean()
        space = self.group.space if self.group else cleaned.get("space")
        if not space and cleaned.get("discoverability") == GroupDiscoverability.SPACE_ONLY:
            self.add_error(
                "discoverability",
                "Un Groupe personnel ne peut pas être limité à un Espace.",
            )
        return cleaned


class JoinRequestForm(forms.Form):
    message = forms.CharField(
        required=False,
        max_length=500,
        label="Message facultatif",
        widget=forms.Textarea(attrs={"rows": 3}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["message"].widget.attrs.setdefault("class", INPUT_CLASS)


class ActivityEligibilityRequestForm(forms.Form):
    activity_id = forms.UUIDField(label="Activity")
