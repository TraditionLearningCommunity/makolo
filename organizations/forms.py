from django import forms

from authorization.constants import (
    LEGACY_ORGANIZATION_ROLE_TO_SYSTEM_ROLE,
    STANDARD_SPACE_ROLE_CODES,
)
from authorization.models import AuthorityScope, Role

from .models import Organization, OrganizationFollow


INPUT_CLASS = (
    "w-full rounded-2xl border border-zinc-300 bg-white px-4 py-3 text-zinc-900 "
    "outline-none transition focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 "
    "dark:border-zinc-700 dark:bg-zinc-900 dark:text-white"
)
CHECKBOX_CLASS = "h-5 w-5 rounded border-zinc-300 text-indigo-600 focus:ring-indigo-500"


class OrganizationForm(forms.ModelForm):
    class Meta:
        model = Organization
        fields = [
            "name",
            "description",
            "website",
            "contact_email",
            "contact_phone",
            "country",
            "city",
            "public_profile",
        ]
        widgets = {"description": forms.Textarea(attrs={"rows": 5})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if not isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs["class"] = INPUT_CLASS


class OrganizationMemberForm(forms.Form):
    email = forms.EmailField(label="E-mail du membre")
    role = forms.ChoiceField(label="Responsabilité")

    def __init__(self, *args, **kwargs):
        # Preserve old POST values such as event_manager during the compatibility
        # window, while every newly rendered form uses canonical role codes.
        if args and args[0] is not None and "role" in args[0]:
            data = args[0].copy()
            data["role"] = LEGACY_ORGANIZATION_ROLE_TO_SYSTEM_ROLE.get(
                data.get("role"), data.get("role")
            )
            args = (data, *args[1:])
        super().__init__(*args, **kwargs)
        roles = Role.objects.filter(
            scope_type=AuthorityScope.SPACE,
            is_system=True,
            is_active=True,
            code__in=STANDARD_SPACE_ROLE_CODES,
        ).order_by("name")
        self.fields["role"].choices = [(role.code, role.name) for role in roles]
        for field in self.fields.values():
            field.widget.attrs["class"] = INPUT_CLASS


class OrganizationFollowPreferenceForm(forms.ModelForm):
    class Meta:
        model = OrganizationFollow
        fields = [
            "notify_new_events",
            "notify_announcements",
            "email_new_events",
            "email_announcements",
        ]
        labels = {
            "notify_new_events": "Nouveaux événements dans Makolo",
            "notify_announcements": "Annonces de l’organisateur dans Makolo",
            "email_new_events": "Recevoir aussi les nouveaux événements par e-mail",
            "email_announcements": "Recevoir aussi les annonces par e-mail",
        }
        help_texts = {
            "email_new_events": "Opt-in propre à cet organisateur. Le réglage global e-mail de votre compte reste prioritaire.",
            "email_announcements": "Vous pouvez suivre un organisateur sans accepter ses e-mails marketing.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = CHECKBOX_CLASS
