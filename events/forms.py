from django import forms

from .models import Event


class EventForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = [
            "title",
            "category",
            "venue",
            "short_description",
            "description",
            "cover_image",
            "visibility",
            "start_at",
            "end_at",
            "registration_start_at",
            "registration_end_at",
            "timezone",
            "capacity",
        ]
        widgets = {
            "start_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "end_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "registration_start_at": forms.DateTimeInput(
                attrs={"type": "datetime-local"}
            ),
            "registration_end_at": forms.DateTimeInput(
                attrs={"type": "datetime-local"}
            ),
            "description": forms.Textarea(attrs={"rows": 6}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        base_class = (
            "w-full rounded-2xl border border-zinc-300 bg-white px-4 py-3 "
            "text-zinc-900 outline-none transition focus:border-indigo-500 "
            "focus:ring-2 focus:ring-indigo-500/20 dark:border-zinc-700 "
            "dark:bg-zinc-900 dark:text-white"
        )
        for field in self.fields.values():
            current = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = f"{current} {base_class}".strip()
