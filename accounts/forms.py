from django import forms
from django.db import transaction

from .models import NotificationPreference, User, UserProfile
from .validators import validate_avatar


INPUT_CLASS = "w-full"
CHECKBOX_CLASS = "h-4 w-4 rounded border-zinc-300"


def _style_form_fields(form):
    for field in form.fields.values():
        if isinstance(field.widget, forms.CheckboxInput):
            field.widget.attrs.setdefault("class", CHECKBOX_CLASS)
        else:
            field.widget.attrs.setdefault("class", INPUT_CLASS)


class AccountRegistrationForm(forms.Form):
    email = forms.EmailField(label="Adresse e-mail")
    username = forms.CharField(max_length=150, label="Identifiant")
    first_name = forms.CharField(max_length=150, required=False, label="Prénom")
    last_name = forms.CharField(max_length=150, required=False, label="Nom")
    phone = forms.CharField(max_length=40, required=False, label="Téléphone")
    password = forms.CharField(label="Mot de passe", widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}))
    password_confirm = forms.CharField(label="Confirmer le mot de passe", widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _style_form_fields(self)
        self.fields["email"].widget.attrs.setdefault("autocomplete", "email")
        self.fields["username"].widget.attrs.setdefault("autocomplete", "username")
        self._serializer = None

    def clean(self):
        cleaned = super().clean()
        if self.errors:
            return cleaned

        # Reuse the API serializer so password policy, uniqueness and account
        # initialization stay identical between web and mobile/API journeys.
        from accounts.api.serializers import RegisterSerializer

        serializer = RegisterSerializer(data=cleaned)
        if not serializer.is_valid():
            for field_name, errors in serializer.errors.items():
                target = field_name if field_name in self.fields else None
                for error in errors:
                    self.add_error(target, str(error))
            return cleaned
        self._serializer = serializer
        return cleaned

    def save(self):
        if self._serializer is None:
            raise ValueError("Le formulaire doit être validé avant la création du compte.")
        return self._serializer.save()


class PasswordForgotForm(forms.Form):
    email = forms.EmailField(label="Adresse e-mail")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _style_form_fields(self)
        self.fields["email"].widget.attrs.setdefault("autocomplete", "email")


class PasswordResetWebForm(forms.Form):
    new_password = forms.CharField(label="Nouveau mot de passe", widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}))
    new_password_confirm = forms.CharField(label="Confirmer le nouveau mot de passe", widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _style_form_fields(self)

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("new_password") != cleaned.get("new_password_confirm"):
            self.add_error("new_password_confirm", "Les mots de passe ne correspondent pas.")
        return cleaned


class AccountDeleteForm(forms.Form):
    password = forms.CharField(label="Mot de passe actuel", widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}))
    confirm = forms.BooleanField(label="Je comprends que mon compte sera désactivé et anonymisé.")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _style_form_fields(self)


class AccountProfileForm(forms.ModelForm):
    company_name = forms.CharField(required=False, label="Entreprise")
    organization_name = forms.CharField(required=False, label="Organisation")
    profession = forms.CharField(required=False, label="Profession")
    country = forms.CharField(required=False, label="Pays")
    city = forms.CharField(required=False, label="Ville")
    address = forms.CharField(required=False, label="Adresse", widget=forms.Textarea(attrs={"rows": 3}))
    public_profile = forms.BooleanField(required=False, label="Profil public")
    searchable = forms.BooleanField(required=False, label="Apparaître dans la recherche")

    class Meta:
        model = User
        fields = [
            "first_name",
            "last_name",
            "phone",
            "birth_date",
            "gender",
            "bio",
            "avatar",
            "website",
            "linkedin_url",
            "facebook_url",
            "instagram_url",
            "x_url",
            "language",
            "timezone",
        ]
        labels = {
            "first_name": "Prénom",
            "last_name": "Nom",
            "phone": "Téléphone",
            "birth_date": "Date de naissance",
            "gender": "Genre",
            "bio": "Présentation",
            "avatar": "Photo de profil",
            "website": "Site web",
            "linkedin_url": "LinkedIn",
            "facebook_url": "Facebook",
            "instagram_url": "Instagram",
            "x_url": "X / Twitter",
            "language": "Langue",
            "timezone": "Fuseau horaire",
        }
        widgets = {
            "birth_date": forms.DateInput(attrs={"type": "date"}),
            "bio": forms.Textarea(attrs={"rows": 4}),
        }

    profile_fields = (
        "company_name",
        "organization_name",
        "profession",
        "country",
        "city",
        "address",
        "public_profile",
        "searchable",
    )
    autocomplete_fields = {
        "first_name": "given-name",
        "last_name": "family-name",
        "phone": "tel",
        "birth_date": "bday",
        "company_name": "organization",
        "organization_name": "organization",
        "profession": "organization-title",
        "country": "country-name",
        "city": "address-level2",
        "address": "street-address",
        "website": "url",
    }

    def __init__(self, *args, profile=None, **kwargs):
        self.profile = profile
        super().__init__(*args, **kwargs)

        if profile and not self.is_bound:
            for field_name in self.profile_fields:
                self.initial[field_name] = getattr(profile, field_name)

        for field_name, field in self.fields.items():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault("class", CHECKBOX_CLASS)
            else:
                widget.attrs.setdefault("class", INPUT_CLASS)
                autocomplete = self.autocomplete_fields.get(field_name)
                if autocomplete and not isinstance(widget, forms.FileInput):
                    widget.attrs.setdefault("autocomplete", autocomplete)

    def clean_avatar(self):
        avatar = self.cleaned_data.get("avatar")
        if avatar:
            validate_avatar(avatar)
        return avatar

    @transaction.atomic
    def save(self, commit=True):
        user = super().save(commit=commit)
        profile = self.profile or UserProfile.objects.get_or_create(user=user)[0]
        for field_name in self.profile_fields:
            setattr(profile, field_name, self.cleaned_data.get(field_name))
        profile.profile_completed = bool(user.first_name and user.last_name and profile.city)
        if commit:
            profile.save()
        self.profile = profile
        return user


class AppearancePreferencesForm(forms.Form):
    APPEARANCE_CHOICES = (
        ("system", "Système"),
        ("light", "Clair"),
        ("dark", "Sombre"),
    )

    appearance = forms.ChoiceField(
        label="Thème",
        choices=APPEARANCE_CHOICES,
        widget=forms.RadioSelect,
    )

    def __init__(self, *args, profile, **kwargs):
        self.profile = profile
        if not args and "data" not in kwargs and "initial" not in kwargs:
            valid = {value for value, _label in self.APPEARANCE_CHOICES}
            current = profile.theme if profile.theme in valid else "system"
            kwargs["initial"] = {"appearance": current}
        super().__init__(*args, **kwargs)

    def save(self):
        self.profile.theme = self.cleaned_data["appearance"]
        self.profile.save(update_fields=["theme", "updated_at"])
        return self.profile


class NotificationPreferencesForm(forms.ModelForm):
    class Meta:
        model = NotificationPreference
        fields = [
            "email_notifications",
            "marketing_notifications",
            "security_notifications",
            "event_notifications",
            "quiet_hours_enabled",
            "quiet_hours_start",
            "quiet_hours_end",
        ]
        labels = {
            "email_notifications": "E-mails",
            "marketing_notifications": "Actualités et offres Makolo",
            "security_notifications": "Sécurité du compte",
            "event_notifications": "Rappels liés à mes activités",
            "quiet_hours_enabled": "Activer les heures calmes",
            "quiet_hours_start": "Début des heures calmes",
            "quiet_hours_end": "Fin des heures calmes",
        }
        widgets = {
            "quiet_hours_start": forms.TimeInput(attrs={"type": "time"}),
            "quiet_hours_end": forms.TimeInput(attrs={"type": "time"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault("class", CHECKBOX_CLASS)
            else:
                field.widget.attrs.setdefault("class", INPUT_CLASS)

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("quiet_hours_enabled") and (
            not cleaned.get("quiet_hours_start") or not cleaned.get("quiet_hours_end")
        ):
            self.add_error(
                "quiet_hours_enabled",
                "Définissez une heure de début et de fin pour activer les heures calmes.",
            )
        return cleaned
