from django import forms

from events.models import Event

from .models import TicketType


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
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "sales_start_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "sales_end_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        queryset = Event.objects.order_by("start_at")
        if user and not user.is_staff:
            queryset = queryset.filter(organizer=user)
        self.fields["event"].queryset = queryset

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
