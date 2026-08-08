from django import forms
from django.contrib.auth import get_user_model

from events.models import Event

from .models import AffiliateCampaign, Partner, ReferralCode


FIELD_CLASS = "mt-1 w-full rounded-2xl border border-zinc-300 bg-white px-4 py-3 text-zinc-900 outline-none focus:border-indigo-500 dark:border-zinc-700 dark:bg-zinc-900 dark:text-white"


class StyledModelForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", FIELD_CLASS)


class PartnerForm(StyledModelForm):
    account_email = forms.EmailField(required=False, label="Compte Makolo (e-mail)", help_text="Optionnel. Lie le partenaire à son portail Makolo.")

    class Meta:
        model = Partner
        fields = ["name", "public_label", "kind", "email", "phone", "notes"]
        labels = {
            "name": "Nom interne",
            "public_label": "Nom public",
            "kind": "Type de partenaire",
            "email": "E-mail de contact",
            "phone": "Téléphone",
            "notes": "Notes internes",
        }
        widgets = {"notes": forms.Textarea(attrs={"rows": 4})}

    def clean_account_email(self):
        value = (self.cleaned_data.get("account_email") or "").strip().lower()
        if not value:
            self.linked_user = None
            return ""
        User = get_user_model()
        user = User.objects.filter(email__iexact=value, is_active=True).first()
        if not user:
            raise forms.ValidationError("Aucun compte Makolo actif ne correspond à cet e-mail.")
        self.linked_user = user
        return value

    def clean(self):
        cleaned = super().clean()
        linked_user = getattr(self, "linked_user", None)
        if not linked_user:
            return cleaned
        contact_email = (cleaned.get("email") or "").strip().lower()
        if contact_email and contact_email != linked_user.email.lower():
            self.add_error("email", "Pour un portail lié, l’e-mail de contact doit correspondre au compte Makolo.")
        elif not contact_email:
            cleaned["email"] = linked_user.email
        return cleaned


class AffiliateCampaignForm(StyledModelForm):
    class Meta:
        model = AffiliateCampaign
        fields = [
            "event",
            "name",
            "status",
            "commission_type",
            "commission_value",
            "commission_currency",
            "attribution_window_days",
            "starts_at",
            "ends_at",
        ]
        labels = {
            "event": "Événement",
            "name": "Nom de la campagne",
            "status": "Statut",
            "commission_type": "Mode de commission",
            "commission_value": "Commission",
            "commission_currency": "Devise (commission fixe)",
            "attribution_window_days": "Fenêtre d’attribution (jours)",
            "starts_at": "Début",
            "ends_at": "Fin",
        }
        widgets = {
            "starts_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "ends_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.organization = organization
        self.fields["event"].queryset = Event.objects.filter(organization=organization).order_by("-start_at") if organization else Event.objects.none()


class ReferralCodeForm(StyledModelForm):
    class Meta:
        model = ReferralCode
        fields = ["partner", "code", "commission_type_override", "commission_value_override", "is_active"]
        labels = {
            "partner": "Partenaire / ambassadeur",
            "code": "Code personnalisé",
            "commission_type_override": "Mode de commission spécifique",
            "commission_value_override": "Valeur spécifique",
            "is_active": "Code actif",
        }
        help_texts = {"code": "Laisser vide pour générer automatiquement un code Makolo."}

    def __init__(self, *args, campaign=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.campaign = campaign
        self.fields["partner"].queryset = Partner.objects.filter(organization=campaign.organization).order_by("name") if campaign else Partner.objects.none()
        self.fields["commission_type_override"].required = False
