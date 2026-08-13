from django import forms
from django.contrib.auth import get_user_model

from authorization.constants import PermissionCode, SystemRoleCode
from authorization.services import space_ids_with_permission
from organizations.models import Organization

from .models import GroupVisibility


User = get_user_model()
INPUT_CLASS = "w-full rounded-xl border px-3 py-2"


class GroupCreateForm(forms.Form):
    name = forms.CharField(max_length=180, label="Nom")
    description = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 4}), label="Description")
    space = forms.ModelChoiceField(queryset=Organization.objects.none(), required=False, label="Espace propriétaire")
    visibility = forms.ChoiceField(choices=GroupVisibility.choices, initial=GroupVisibility.PRIVATE, label="Visibilité")

    def __init__(self, *args, actor=None, **kwargs):
        super().__init__(*args, **kwargs)
        ids = space_ids_with_permission(actor, PermissionCode.SPACE_GROUPS_MANAGE) if actor else []
        queryset = Organization.objects.all() if ids is None else Organization.objects.filter(pk__in=ids)
        self.fields["space"].queryset = queryset.order_by("name")
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", INPUT_CLASS)

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("space"):
            cleaned["visibility"] = GroupVisibility.PRIVATE
        return cleaned


class GroupUpdateForm(forms.Form):
    name = forms.CharField(max_length=180, label="Nom")
    description = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 4}), label="Description")
    visibility = forms.ChoiceField(choices=GroupVisibility.choices, label="Visibilité")

    def __init__(self, *args, group=None, **kwargs):
        if group and "initial" not in kwargs:
            kwargs["initial"] = {
                "name": group.name,
                "description": group.description,
                "visibility": group.visibility,
            }
        super().__init__(*args, **kwargs)
        if group and group.owner_profile_id:
            self.fields["visibility"].choices = [(GroupVisibility.PRIVATE, "Privé")]
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", INPUT_CLASS)


class AddMemberForm(forms.Form):
    email = forms.EmailField(label="E-mail du Profil Makolo")
    external_reference = forms.CharField(required=False, max_length=160, label="Référence externe")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", INPUT_CLASS)

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        try:
            self.profile = User.objects.get(email__iexact=email, is_active=True)
        except User.DoesNotExist as exc:
            raise forms.ValidationError("Aucun Profil Makolo actif ne correspond à cet e-mail. Utilisez plutôt une invitation.") from exc
        return email


class GroupInvitationForm(forms.Form):
    email = forms.EmailField(required=False, label="E-mail")
    phone = forms.CharField(required=False, max_length=40, label="Téléphone")
    external_reference = forms.CharField(required=False, max_length=160, label="Référence externe")
    first_name = forms.CharField(required=False, max_length=100, label="Prénom (affichage)")
    last_name = forms.CharField(required=False, max_length=100, label="Nom (affichage)")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", INPUT_CLASS)

    def clean(self):
        cleaned = super().clean()
        if not any(cleaned.get(field) for field in ("email", "phone", "external_reference")):
            raise forms.ValidationError("Indiquez au moins un e-mail, un téléphone ou une référence externe.")
        return cleaned


class GroupImportForm(forms.Form):
    csv_file = forms.FileField(label="Fichier CSV")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["csv_file"].widget.attrs.update({"accept": ".csv,text/csv", "class": INPUT_CLASS})


class SnapshotForm(forms.Form):
    name = forms.CharField(required=False, max_length=180, label="Nom du snapshot")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["name"].widget.attrs.setdefault("class", INPUT_CLASS)


class TransferOwnershipForm(forms.Form):
    email = forms.EmailField(label="Nouveau propriétaire")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].widget.attrs.setdefault("class", INPUT_CLASS)

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        try:
            self.new_owner = User.objects.get(email__iexact=email, is_active=True)
        except User.DoesNotExist as exc:
            raise forms.ValidationError("Aucun Profil Makolo actif ne correspond à cet e-mail.") from exc
        return email


class GroupResponsibilityForm(forms.Form):
    email = forms.EmailField(label="Profil")
    role_code = forms.ChoiceField(
        label="Responsabilité",
        choices=[
            (SystemRoleCode.GROUP_ADMIN, "Administrateur du Groupe"),
            (SystemRoleCode.GROUP_MODERATOR, "Modérateur du Groupe"),
        ],
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", INPUT_CLASS)

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        try:
            self.profile = User.objects.get(email__iexact=email, is_active=True)
        except User.DoesNotExist as exc:
            raise forms.ValidationError("Aucun Profil Makolo actif ne correspond à cet e-mail.") from exc
        return email
