from django import forms

from .models import Organization, OrganizationFollow, OrganizationRole


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
    role = forms.ChoiceField(label="Rôle", choices=OrganizationRole.choices)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
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
