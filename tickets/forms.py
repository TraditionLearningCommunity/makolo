from django import forms

from events.models import Event

from .models import TicketType


INPUT_CLASS = (
    "w-full rounded-2xl border border-zinc-300 bg-white px-4 py-3.5 "
    "text-zinc-900 outline-none transition placeholder:text-zinc-400 "
    "focus:border-indigo-500 focus:ring-4 focus:ring-indigo-500/10 "
    "dark:border-zinc-700 dark:bg-zinc-900 dark:text-white "
    "dark:focus:border-indigo-500"
)
CHECKBOX_CLASS = (
    "h-6 w-6 rounded-lg border-zinc-300 text-indigo-600 "
    "focus:ring-indigo-500 dark:border-zinc-700 dark:bg-zinc-900"
)


class TicketTypeForm(forms.ModelForm):
    class Meta:
        model = TicketType
        fields = [
            "event",
            "name",
            "description",
            "price",
            "currency",
            "quantity_total",
            "sales_start_at",
            "sales_end_at",
            "min_per_order",
            "max_per_order",
            "is_active",
        ]
        labels = {
            "event": "Événement",
            "name": "Nom du billet",
            "description": "Description",
            "price": "Prix",
            "currency": "Devise",
            "quantity_total": "Stock total",
            "sales_start_at": "Début des ventes",
            "sales_end_at": "Fin des ventes",
            "min_per_order": "Minimum par commande",
            "max_per_order": "Maximum par commande",
            "is_active": "Billet actif",
        }
        help_texts = {
            "name": "Ex. Standard, VIP, Early Bird, Étudiant…",
            "currency": "Code ISO à 3 lettres, par exemple USD, CDF ou EUR.",
            "sales_start_at": "Optionnel. Laissez vide pour vendre dès que l'événement accepte les inscriptions.",
            "sales_end_at": "Optionnel. Laissez vide pour suivre la fermeture des inscriptions de l'événement.",
            "min_per_order": "Nombre minimum de billets autorisé dans une commande.",
            "max_per_order": "Nombre maximum de billets autorisé dans une commande.",
        }
        widgets = {
            "event": forms.Select(attrs={"class": INPUT_CLASS}),
            "name": forms.TextInput(
                attrs={"class": INPUT_CLASS, "placeholder": "Ex. Pass Standard"}
            ),
            "description": forms.Textarea(
                attrs={
                    "class": INPUT_CLASS,
                    "rows": 4,
                    "placeholder": "Décrivez les avantages ou conditions de ce billet.",
                }
            ),
            "price": forms.NumberInput(
                attrs={"class": INPUT_CLASS, "min": "0", "step": "0.01"}
            ),
            "currency": forms.TextInput(
                attrs={
                    "class": INPUT_CLASS,
                    "maxlength": "3",
                    "placeholder": "USD",
                    "style": "text-transform: uppercase",
                }
            ),
            "quantity_total": forms.NumberInput(
                attrs={"class": INPUT_CLASS, "min": "1", "placeholder": "Illimité"}
            ),
            "sales_start_at": forms.DateTimeInput(
                attrs={"class": INPUT_CLASS, "type": "datetime-local"}
            ),
            "sales_end_at": forms.DateTimeInput(
                attrs={"class": INPUT_CLASS, "type": "datetime-local"}
            ),
            "min_per_order": forms.NumberInput(
                attrs={"class": INPUT_CLASS, "min": "1"}
            ),
            "max_per_order": forms.NumberInput(
                attrs={"class": INPUT_CLASS, "min": "1"}
            ),
            "is_active": forms.CheckboxInput(attrs={"class": CHECKBOX_CLASS}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        queryset = Event.objects.order_by("start_at")
        if user and not user.is_staff:
            queryset = queryset.filter(organizer=user)
        self.fields["event"].queryset = queryset

    def clean_currency(self):
        return (self.cleaned_data.get("currency") or "USD").upper()

    def clean(self):
        cleaned = super().clean()
        event = cleaned.get("event")
        if event and self.instance.pk and self.instance.event_id != event.pk:
            if self.instance.reserved_quantity or self.instance.issued_quantity:
                self.add_error(
                    "event",
                    "Un type de billet déjà utilisé ne peut pas changer d’événement.",
                )
        return cleaned
