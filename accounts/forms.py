from django import forms
from django.db import transaction

from .models import NotificationPreference, User, UserProfile
from .validators import validate_avatar


INPUT_CLASS = "w-full"
CHECKBOX_CLASS = "h-4 w-4 rounded border-zinc-300"


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
                if not isinstance(widget, forms.FileInput):
                    widget.attrs.setdefault("autocomplete", "off")

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


class NotificationPreferencesForm(forms.ModelForm):
    class Meta:
        model = NotificationPreference
        fields = [
            "email_notifications",
            "sms_notifications",
            "push_notifications",
            "marketing_notifications",
            "security_notifications",
            "event_notifications",
            "quiet_hours_enabled",
            "quiet_hours_start",
            "quiet_hours_end",
        ]
        labels = {
            "email_notifications": "E-mails",
            "sms_notifications": "SMS",
            "push_notifications": "Notifications push",
            "marketing_notifications": "Actualités et offres Makolo",
            "security_notifications": "Sécurité du compte",
            "event_notifications": "Rappels liés aux événements",
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
