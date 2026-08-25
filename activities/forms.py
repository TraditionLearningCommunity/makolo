from django import forms

from authorization.constants import PermissionCode
from authorization.services import space_ids_with_permission
from organizations.models import Organization

from .models import ActivityVisibility


class ActivityCreateForm(forms.Form):
    organization = forms.ModelChoiceField(
        queryset=Organization.objects.none(),
        required=False,
        empty_label="Moi-même",
        label="Organiser en tant que",
        help_text="Choisissez votre Profil ou un Espace pour lequel vous avez une autorité active.",
    )
    title = forms.CharField(max_length=220, label="Titre")
    short_description = forms.CharField(max_length=320, required=False, label="Description courte")
    description = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 6}), label="Description")
    visibility = forms.ChoiceField(
        choices=ActivityVisibility.choices,
        initial=ActivityVisibility.PRIVATE,
        label="Visibilité",
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user and user.is_authenticated:
            ids = space_ids_with_permission(user, PermissionCode.SPACE_ACTIVITIES_MANAGE)
            queryset = Organization.objects.all() if ids is None else Organization.objects.filter(pk__in=ids)
            self.fields["organization"].queryset = queryset.order_by("name")
        base_class = (
            "w-full rounded-2xl border border-zinc-300 bg-white px-4 py-3 "
            "text-zinc-900 outline-none transition focus:border-indigo-500 "
            "focus:ring-2 focus:ring-indigo-500/20 dark:border-zinc-700 "
            "dark:bg-zinc-900 dark:text-white"
        )
        for field in self.fields.values():
            field.widget.attrs["class"] = f"{field.widget.attrs.get('class', '')} {base_class}".strip()
