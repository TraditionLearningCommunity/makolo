from django import forms

from .models import Organization, OrganizationRole


INPUT_CLASS = (
    "w-full rounded-2xl border border-zinc-300 bg-white px-4 py-3 text-zinc-900 "
    "outline-none transition focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 "
    "dark:border-zinc-700 dark:bg-zinc-900 dark:text-white"
)


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
