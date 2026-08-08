from django import forms
from django.contrib.auth import get_user_model

from .forms import FIELD_CLASS, StyledModelForm
from .models import Partner


class PartnerUpdateForm(StyledModelForm):
    account_email = forms.EmailField(
        required=False,
        label="Compte Makolo (e-mail)",
        help_text="Laisser vide pour retirer l'accès au portail partenaire.",
    )

    class Meta:
        model = Partner
        fields = ["name", "public_label", "kind", "status", "email", "phone", "notes"]
        labels = {
            "name": "Nom interne",
            "public_label": "Nom public",
            "kind": "Type de partenaire",
            "status": "Statut",
            "email": "E-mail de contact",
            "phone": "Téléphone",
            "notes": "Notes internes",
        }
        widgets = {"notes": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.user_id:
            self.fields["account_email"].initial = self.instance.user.email

    def clean(self):
        cleaned = super().clean()
        account_email = (cleaned.get("account_email") or "").strip().lower()
        self.linked_user = None
        if account_email:
            User = get_user_model()
            self.linked_user = User.objects.filter(email__iexact=account_email, is_active=True).first()
            if not self.linked_user:
                self.add_error("account_email", "Aucun compte Makolo actif ne correspond à cet e-mail.")
            contact_email = (cleaned.get("email") or "").strip().lower()
            if self.linked_user and contact_email and contact_email != self.linked_user.email.lower():
                self.add_error("email", "Pour un portail lié, l’e-mail de contact doit correspondre au compte Makolo.")
            elif self.linked_user and not contact_email:
                cleaned["email"] = self.linked_user.email
        return cleaned
