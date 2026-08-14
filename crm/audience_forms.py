from django import forms
from django.contrib.auth import get_user_model

from groups.models import Group, GroupSnapshot


INPUT_CLASS = (
    "w-full rounded-2xl border border-zinc-300 bg-white px-4 py-3 text-zinc-900 "
    "dark:border-zinc-700 dark:bg-zinc-900 dark:text-white"
)


class AudienceCreateForm(forms.Form):
    SOURCE_STATIC = "static"
    SOURCE_GROUP = "group"
    SOURCE_SNAPSHOT = "snapshot"
    SOURCE_CHOICES = [
        (SOURCE_STATIC, "Audience statique"),
        (SOURCE_GROUP, "Membres actuels d’un Groupe"),
        (SOURCE_SNAPSHOT, "Snapshot de Groupe"),
    ]

    name = forms.CharField(max_length=160, label="Nom")
    description = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}), label="Description")
    source = forms.ChoiceField(choices=SOURCE_CHOICES, initial=SOURCE_STATIC, label="Source")
    profiles = forms.ModelMultipleChoiceField(
        queryset=get_user_model().objects.none(),
        required=False,
        label="Contacts",
        help_text="Uniquement les Profils déjà connus de cet Espace.",
    )
    group = forms.ModelChoiceField(queryset=Group.objects.none(), required=False, label="Groupe")
    snapshot = forms.ModelChoiceField(queryset=GroupSnapshot.objects.none(), required=False, label="Snapshot")

    def __init__(self, *args, organization, **kwargs):
        super().__init__(*args, **kwargs)
        self.organization = organization
        self.fields["profiles"].queryset = get_user_model().objects.filter(
            crm_contact_profiles__organization=organization
        ).distinct().order_by("email")
        self.fields["group"].queryset = Group.objects.filter(space=organization).order_by("name")
        self.fields["snapshot"].queryset = GroupSnapshot.objects.filter(group__space=organization).select_related("group").order_by("-created_at")
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", INPUT_CLASS)

    def clean(self):
        cleaned = super().clean()
        source = cleaned.get("source")
        if source == self.SOURCE_GROUP and not cleaned.get("group"):
            self.add_error("group", "Choisissez un Groupe appartenant à cet Espace.")
        if source == self.SOURCE_SNAPSHOT and not cleaned.get("snapshot"):
            self.add_error("snapshot", "Choisissez un snapshot appartenant à cet Espace.")
        return cleaned
