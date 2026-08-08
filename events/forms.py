from django import forms

from organizations.models import Organization, OrganizationRole

from .models import Event


class EventForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = [
            "organization",
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
            "registration_start_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "registration_end_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "description": forms.Textarea(attrs={"rows": 6}),
        }
        labels = {"organization": "Organisation organisatrice"}

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user and user.is_authenticated:
            if user.is_staff:
                queryset = Organization.objects.all()
            else:
                queryset = Organization.objects.filter(
                    memberships__user=user,
                    memberships__is_active=True,
                    memberships__role__in=[
                        OrganizationRole.OWNER,
                        OrganizationRole.ADMIN,
                        OrganizationRole.EVENT_MANAGER,
                    ],
                ).distinct()
            self.fields["organization"].queryset = queryset
            self.fields["organization"].required = True
            if not self.instance.pk and queryset.count() == 1:
                self.fields["organization"].initial = queryset.first()

        base_class = (
            "w-full rounded-2xl border border-zinc-300 bg-white px-4 py-3 "
            "text-zinc-900 outline-none transition focus:border-indigo-500 "
            "focus:ring-2 focus:ring-indigo-500/20 dark:border-zinc-700 "
            "dark:bg-zinc-900 dark:text-white"
        )
        for field in self.fields.values():
            current = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = f"{current} {base_class}".strip()
