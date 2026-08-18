from django import forms

from authorization.constants import PermissionCode
from authorization.services import space_ids_with_permission
from organizations.models import Organization

from .models import EventCategory, EventVenue, EventVisibility


class EventForm(forms.Form):
    """Event vocabulary over Activity/Occurrence/Event composition."""

    organization = forms.ModelChoiceField(queryset=Organization.objects.none(), label="Organisation organisatrice")
    title = forms.CharField(max_length=220, label="Titre")
    category = forms.ModelChoiceField(queryset=EventCategory.objects.filter(is_active=True), required=False, label="Catégorie")
    venue = forms.ModelChoiceField(queryset=EventVenue.objects.filter(is_active=True), required=False, label="Lieu")
    short_description = forms.CharField(max_length=320, required=False, label="Description courte")
    description = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 6}), label="Description")
    cover_image = forms.ImageField(required=False, label="Image de couverture")
    visibility = forms.ChoiceField(choices=EventVisibility.choices, initial=EventVisibility.PUBLIC, label="Visibilité")
    start_at = forms.DateTimeField(widget=forms.DateTimeInput(attrs={"type": "datetime-local"}), label="Début")
    end_at = forms.DateTimeField(widget=forms.DateTimeInput(attrs={"type": "datetime-local"}), label="Fin")
    registration_start_at = forms.DateTimeField(required=False, widget=forms.DateTimeInput(attrs={"type": "datetime-local"}), label="Début des inscriptions")
    registration_end_at = forms.DateTimeField(required=False, widget=forms.DateTimeInput(attrs={"type": "datetime-local"}), label="Fin des inscriptions")
    timezone = forms.CharField(max_length=100, initial="Africa/Lubumbashi", label="Fuseau horaire")

    def __init__(self, *args, user=None, instance=None, **kwargs):
        self.instance = instance
        super().__init__(*args, **kwargs)
        if user and user.is_authenticated:
            if user.is_staff:
                queryset = Organization.objects.all()
            else:
                space_ids = space_ids_with_permission(user, PermissionCode.SPACE_ACTIVITIES_MANAGE)
                queryset = Organization.objects.all() if space_ids is None else Organization.objects.filter(pk__in=space_ids)
            self.fields["organization"].queryset = queryset.distinct()
            if not instance and queryset.count() == 1:
                self.fields["organization"].initial = queryset.first()

        if instance is not None:
            self.initial.update(
                {
                    "organization": instance.organization,
                    "title": instance.title,
                    "category": instance.category,
                    "venue": instance.venue,
                    "short_description": instance.short_description,
                    "description": instance.description,
                    "visibility": instance.visibility,
                    "start_at": instance.start_at,
                    "end_at": instance.end_at,
                    "registration_start_at": instance.registration_start_at,
                    "registration_end_at": instance.registration_end_at,
                    "timezone": instance.timezone,
                }
            )

        base_class = (
            "w-full rounded-2xl border border-zinc-300 bg-white px-4 py-3 "
            "text-zinc-900 outline-none transition focus:border-indigo-500 "
            "focus:ring-2 focus:ring-indigo-500/20 dark:border-zinc-700 "
            "dark:bg-zinc-900 dark:text-white"
        )
        for field in self.fields.values():
            current = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = f"{current} {base_class}".strip()

    def clean(self):
        cleaned = super().clean()
        start_at = cleaned.get("start_at")
        end_at = cleaned.get("end_at")
        registration_start_at = cleaned.get("registration_start_at")
        registration_end_at = cleaned.get("registration_end_at")
        if start_at and end_at and end_at <= start_at:
            self.add_error("end_at", "La fin doit être postérieure au début.")
        if registration_start_at and registration_end_at and registration_end_at <= registration_start_at:
            self.add_error("registration_end_at", "La fin des inscriptions doit être postérieure à leur début.")
        if registration_end_at and end_at and registration_end_at > end_at:
            self.add_error("registration_end_at", "Les inscriptions ne peuvent pas se terminer après l’événement.")
        if registration_start_at and end_at and registration_start_at >= end_at:
            self.add_error("registration_start_at", "Les inscriptions doivent commencer avant la fin de l’événement.")
        return cleaned
