from django import forms
from django.contrib.auth import get_user_model
from django.db.models import Q

from events.selectors import get_manageable_events

from .models import ScannerAssignment


INPUT_CLASS = (
    "w-full rounded-2xl border border-zinc-300 bg-white px-4 py-3 "
    "text-zinc-900 outline-none transition focus:border-indigo-500 "
    "focus:ring-4 focus:ring-indigo-500/10 dark:border-zinc-700 "
    "dark:bg-zinc-900 dark:text-white"
)


class ScannerAssignmentForm(forms.ModelForm):
    class Meta:
        model = ScannerAssignment
        fields = [
            "event",
            "agent",
            "label",
            "valid_from",
            "valid_until",
            "is_active",
            "notes",
        ]
        widgets = {
            "event": forms.Select(attrs={"class": INPUT_CLASS}),
            "agent": forms.Select(attrs={"class": INPUT_CLASS}),
            "label": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "valid_from": forms.DateTimeInput(
                attrs={"class": INPUT_CLASS, "type": "datetime-local"},
                format="%Y-%m-%dT%H:%M",
            ),
            "valid_until": forms.DateTimeInput(
                attrs={"class": INPUT_CLASS, "type": "datetime-local"},
                format="%Y-%m-%dT%H:%M",
            ),
            "is_active": forms.CheckboxInput(
                attrs={"class": "h-5 w-5 rounded border-zinc-300 text-indigo-600"}
            ),
            "notes": forms.Textarea(attrs={"class": INPUT_CLASS, "rows": 3}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields["valid_from"].input_formats = ["%Y-%m-%dT%H:%M"]
        self.fields["valid_until"].input_formats = ["%Y-%m-%dT%H:%M"]

        if user is not None:
            self.fields["event"].queryset = get_manageable_events(user).order_by(
                "start_at", "title"
            )

        User = get_user_model()
        self.fields["agent"].queryset = (
            User.objects.filter(is_active=True)
            .filter(
                Q(is_staff=True)
                | Q(is_scanner_agent=True)
                | Q(roles__code="scanner-agent", roles__is_active=True)
            )
            .distinct()
            .order_by("first_name", "last_name", "username")
        )
