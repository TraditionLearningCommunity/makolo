from datetime import timedelta
from zoneinfo import ZoneInfo

from django import forms

from activities.models import OccurrenceScheduleFrequency, OccurrenceTimingKind
from authorization.constants import PermissionCode
from authorization.services import space_ids_with_permission
from organizations.models import Organization

from .models import EventCategory, EventStatus, EventVenue, EventVisibility


WEEKDAY_CHOICES = (
    (0, "Lundi"),
    (1, "Mardi"),
    (2, "Mercredi"),
    (3, "Jeudi"),
    (4, "Vendredi"),
    (5, "Samedi"),
    (6, "Dimanche"),
)
COMPLETED_EVENT_LOCKED_FORM_FIELDS = (
    "organization",
    "venue",
    "timing_kind",
    "start_date",
    "start_time",
    "end_date",
    "end_time",
    "start_at",
    "end_at",
    "repeat",
    "frequency",
    "interval",
    "weekdays",
    "repeat_until",
    "registration_start_at",
    "registration_end_at",
    "timezone",
)


class EventForm(forms.Form):
    """Event vocabulary over Activity + one or many Occurrences."""

    organization = forms.ModelChoiceField(
        queryset=Organization.objects.none(),
        required=False,
        empty_label="Moi-même",
        label="Organiser en tant que",
        help_text="Votre Profil organise personnellement l’événement, ou choisissez un Espace que vous êtes autorisé à représenter.",
    )
    title = forms.CharField(max_length=220, label="Titre")
    category = forms.ModelChoiceField(queryset=EventCategory.objects.filter(is_active=True), required=False, label="Catégorie")
    venue = forms.ModelChoiceField(queryset=EventVenue.objects.filter(is_active=True), required=False, label="Lieu par défaut")
    short_description = forms.CharField(max_length=320, required=False, label="Description courte")
    description = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 6}), label="Description")
    cover_image = forms.ImageField(required=False, label="Image de couverture")
    visibility = forms.ChoiceField(choices=EventVisibility.choices, initial=EventVisibility.PUBLIC, label="Visibilité")

    timing_kind = forms.ChoiceField(choices=OccurrenceTimingKind.choices, initial=OccurrenceTimingKind.EXACT, label="Précision de l’horaire")
    start_date = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}), label="Date de début")
    start_time = forms.TimeField(required=False, widget=forms.TimeInput(attrs={"type": "time"}), label="Heure de début")
    end_date = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}), label="Date de fin")
    end_time = forms.TimeField(required=False, widget=forms.TimeInput(attrs={"type": "time"}), label="Heure de fin")
    # Compatibility-only inputs for older clients/tests. New HTML uses split fields.
    start_at = forms.DateTimeField(required=False, widget=forms.HiddenInput())
    end_at = forms.DateTimeField(required=False, widget=forms.HiddenInput())
    timezone = forms.CharField(max_length=100, initial="Africa/Lubumbashi", label="Fuseau horaire")

    repeat = forms.BooleanField(required=False, label="Répéter cette date")
    frequency = forms.ChoiceField(choices=OccurrenceScheduleFrequency.choices, required=False, label="Répétition")
    interval = forms.IntegerField(required=False, min_value=1, initial=1, label="Tous les")
    weekdays = forms.MultipleChoiceField(choices=WEEKDAY_CHOICES, required=False, label="Jours de la semaine")
    repeat_until = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}), label="Répéter jusqu’au")

    registration_start_at = forms.DateTimeField(required=False, widget=forms.DateTimeInput(attrs={"type": "datetime-local"}), label="Début des inscriptions")
    registration_end_at = forms.DateTimeField(required=False, widget=forms.DateTimeInput(attrs={"type": "datetime-local"}), label="Fin des inscriptions")

    def __init__(self, *args, user=None, instance=None, **kwargs):
        self.instance = instance
        super().__init__(*args, **kwargs)
        if user and user.is_authenticated:
            space_ids = space_ids_with_permission(user, PermissionCode.SPACE_ACTIVITIES_MANAGE)
            queryset = Organization.objects.all() if space_ids is None else Organization.objects.filter(pk__in=space_ids)
            self.fields["organization"].queryset = queryset.distinct().order_by("name")

        if instance is not None:
            occurrence = instance.primary_occurrence
            self.initial.update(
                {
                    "organization": instance.organization,
                    "title": instance.title,
                    "category": instance.category,
                    "venue": instance.venue,
                    "short_description": instance.short_description,
                    "description": instance.description,
                    "visibility": instance.visibility,
                    "registration_start_at": instance.registration_start_at,
                    "registration_end_at": instance.registration_end_at,
                }
            )
            if occurrence is not None:
                self.initial.update(
                    {
                        "timing_kind": occurrence.timing_kind,
                        "start_date": occurrence.start_date,
                        "start_time": occurrence.start_time,
                        "end_date": occurrence.end_date,
                        "end_time": occurrence.end_time,
                        "timezone": occurrence.timezone,
                    }
                )
            if instance.activity.occurrences.count() > 1:
                # Multi-date editing is occurrence-scoped from the detail surface.
                for name in (
                    "timing_kind", "start_date", "start_time", "end_date", "end_time",
                    "start_at", "end_at", "repeat", "frequency", "interval", "weekdays", "repeat_until", "timezone",
                ):
                    self.fields.pop(name, None)
            if instance.status == EventStatus.COMPLETED:
                for field_name in COMPLETED_EVENT_LOCKED_FORM_FIELDS:
                    self.fields.pop(field_name, None)

        base_class = (
            "w-full rounded-2xl border border-zinc-300 bg-white px-4 py-3 "
            "text-zinc-900 outline-none transition focus:border-indigo-500 "
            "focus:ring-2 focus:ring-indigo-500/20 dark:border-zinc-700 "
            "dark:bg-zinc-900 dark:text-white"
        )
        for field in self.fields.values():
            if isinstance(field.widget, forms.HiddenInput):
                continue
            current = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = f"{current} {base_class}".strip()

    def clean(self):
        cleaned = super().clean()
        if "start_date" not in self.fields:
            return cleaned

        timezone_name = (cleaned.get("timezone") or "Africa/Lubumbashi").strip()
        try:
            zone = ZoneInfo(timezone_name)
        except Exception:
            self.add_error("timezone", "Fuseau horaire invalide.")
            zone = None

        # Legacy datetime inputs are converted into the same structured contract.
        legacy_start = cleaned.get("start_at")
        legacy_end = cleaned.get("end_at")
        if legacy_start and not cleaned.get("start_date") and zone is not None:
            local = legacy_start.astimezone(zone)
            cleaned["start_date"] = local.date()
            cleaned["start_time"] = local.timetz().replace(tzinfo=None)
            cleaned["timing_kind"] = OccurrenceTimingKind.EXACT
        if legacy_end and not cleaned.get("end_date") and zone is not None:
            local = legacy_end.astimezone(zone)
            cleaned["end_date"] = local.date()
            cleaned["end_time"] = local.timetz().replace(tzinfo=None)

        start_date = cleaned.get("start_date")
        start_time = cleaned.get("start_time")
        end_date = cleaned.get("end_date")
        end_time = cleaned.get("end_time")
        timing_kind = cleaned.get("timing_kind") or OccurrenceTimingKind.EXACT

        if self.instance is None and not start_date:
            self.add_error("start_date", "La date de début est obligatoire.")
        if timing_kind == OccurrenceTimingKind.EXACT and start_date and not start_time:
            self.add_error("start_time", "Indiquez une heure ou choisissez « heure à confirmer ».")
        if timing_kind != OccurrenceTimingKind.EXACT and (start_time or end_time):
            self.add_error("start_time", "Une date sans heure exacte ne doit pas contenir d’heure.")
        if end_date and start_date and end_date < start_date:
            self.add_error("end_date", "La fin doit être postérieure ou égale au début.")
        if timing_kind == OccurrenceTimingKind.EXACT and start_date and start_time and end_time:
            effective_end_date = end_date or start_date
            if effective_end_date == start_date and end_time <= start_time:
                self.add_error("end_time", "La fin doit être postérieure au début.")

        repeat = cleaned.get("repeat")
        if repeat:
            frequency = cleaned.get("frequency")
            if not frequency:
                self.add_error("frequency", "Choisissez une fréquence de répétition.")
            if not cleaned.get("repeat_until"):
                self.add_error("repeat_until", "Une répétition doit être bornée par une date de fin.")
            elif start_date and cleaned["repeat_until"] < start_date:
                self.add_error("repeat_until", "La répétition doit se terminer après son début.")
            if frequency == OccurrenceScheduleFrequency.WEEKLY and not cleaned.get("weekdays"):
                self.add_error("weekdays", "Choisissez au moins un jour de la semaine.")

        registration_start_at = cleaned.get("registration_start_at")
        registration_end_at = cleaned.get("registration_end_at")
        if registration_start_at and registration_end_at and registration_end_at <= registration_start_at:
            self.add_error("registration_end_at", "La fin des inscriptions doit être postérieure au début.")
        return cleaned
