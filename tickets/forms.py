from django import forms

from activities.models import Occurrence
from events.models import Event
from events.selectors import get_manageable_events


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


class TicketTypeForm(forms.Form):
    """Event-facing ticket vocabulary; Offer/Capacity own occurrence scope."""

    event = forms.ModelChoiceField(queryset=Event.objects.none(), label="Événement")
    occurrence = forms.ModelChoiceField(
        queryset=Occurrence.objects.none(),
        required=False,
        label="Date / séance",
    )
    name = forms.CharField(max_length=140, label="Nom du billet")
    description = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 4}), label="Description")
    price = forms.DecimalField(min_value=0, max_digits=12, decimal_places=2, label="Prix")
    currency = forms.CharField(max_length=3, initial="USD", label="Devise")
    quantity_total = forms.IntegerField(required=False, min_value=1, label="Stock total")
    sales_start_at = forms.DateTimeField(required=False, widget=forms.DateTimeInput(attrs={"type": "datetime-local"}), label="Début des ventes")
    sales_end_at = forms.DateTimeField(required=False, widget=forms.DateTimeInput(attrs={"type": "datetime-local"}), label="Fin des ventes")
    min_per_order = forms.IntegerField(min_value=1, initial=1, label="Minimum par commande")
    max_per_order = forms.IntegerField(min_value=1, initial=10, label="Maximum par commande")
    is_active = forms.BooleanField(required=False, initial=True, label="Billet actif")
    is_public = forms.BooleanField(required=False, initial=True, label="Visible publiquement")

    def __init__(self, *args, user=None, instance=None, **kwargs):
        self.instance = instance
        super().__init__(*args, **kwargs)
        queryset = Event.objects.order_by("activity__occurrences__start_date", "activity__occurrences__start_time")
        if user:
            queryset = get_manageable_events(user).order_by("activity__occurrences__start_date", "activity__occurrences__start_time")
        self.fields["event"].queryset = queryset.distinct()

        event_id = None
        if self.is_bound:
            event_id = self.data.get("event")
        elif instance is not None:
            event_id = instance.event_id
        if event_id:
            self.fields["occurrence"].queryset = Occurrence.objects.filter(activity__event_vertical__pk=event_id).order_by("start_date", "start_time", "id")

        if instance is not None:
            self.initial.update(
                {
                    "event": instance.event,
                    "occurrence": instance.offer.occurrence,
                    "name": instance.name,
                    "description": instance.description,
                    "price": instance.price,
                    "currency": instance.currency,
                    "quantity_total": instance.quantity_total,
                    "sales_start_at": instance.sales_start_at,
                    "sales_end_at": instance.sales_end_at,
                    "min_per_order": instance.min_per_order,
                    "max_per_order": instance.max_per_order,
                    "is_active": instance.is_active,
                    "is_public": instance.is_public,
                }
            )

        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs["class"] = CHECKBOX_CLASS
            else:
                field.widget.attrs["class"] = INPUT_CLASS
        self.fields["price"].widget.attrs.update({"min": "0", "step": "0.01"})
        self.fields["currency"].widget.attrs.update({"maxlength": "3", "placeholder": "USD", "style": "text-transform: uppercase"})
        self.fields["quantity_total"].widget.attrs.update({"min": "1", "placeholder": "Illimité"})
        self.fields["sales_start_at"].widget.attrs["type"] = "datetime-local"
        self.fields["sales_end_at"].widget.attrs["type"] = "datetime-local"

    def clean_currency(self):
        return (self.cleaned_data.get("currency") or "USD").upper()

    def clean(self):
        cleaned = super().clean()
        event = cleaned.get("event")
        occurrence = cleaned.get("occurrence")
        if event and self.instance and self.instance.pk and self.instance.event_id != event.pk:
            self.add_error("event", "Un type de billet existant ne peut pas changer d’événement.")

        if event and occurrence is None:
            if self.instance and self.instance.pk and self.instance.event_id == event.pk:
                occurrence = self.instance.offer.occurrence
            else:
                occurrences = list(
                    event.activity.occurrences.order_by("start_date", "start_time", "id")[:2]
                )
                if len(occurrences) == 1:
                    occurrence = occurrences[0]
                elif not occurrences:
                    self.add_error("occurrence", "Cet événement ne possède aucune date / séance à cibler.")
                else:
                    self.add_error("occurrence", "Choisissez la date / séance ciblée par ce type de billet.")
            if occurrence is not None:
                cleaned["occurrence"] = occurrence

        if event and occurrence and occurrence.activity_id != event.activity_id:
            self.add_error("occurrence", "Cette date n’appartient pas à l’événement sélectionné.")
        if self.instance and occurrence and self.instance.offer.occurrence_id != occurrence.pk:
            self.add_error("occurrence", "Un type de billet existant ne peut pas changer de séance.")
        minimum = cleaned.get("min_per_order")
        maximum = cleaned.get("max_per_order")
        if minimum and maximum and maximum < minimum:
            self.add_error("max_per_order", "Le maximum doit être supérieur ou égal au minimum.")
        start = cleaned.get("sales_start_at")
        end = cleaned.get("sales_end_at")
        if start and end and end <= start:
            self.add_error("sales_end_at", "La fin des ventes doit être postérieure au début.")
        return cleaned
