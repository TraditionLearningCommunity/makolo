from django import forms
from django.core.exceptions import ValidationError

from objectives.models import Dossier

from .models import DiscoveryWatch
from .watches import normalize_watch_criteria

WHEN_CHOICES = [("", "À venir"), ("today", "Aujourd’hui"), ("tomorrow", "Demain"), ("weekend", "Ce week-end"), ("week", "Cette semaine")]
PERIOD_CHOICES = [("", "Toute la journée"), ("morning", "Matin"), ("afternoon", "Après-midi"), ("evening", "Soir")]
VERTICAL_CHOICES = [("", "Tout"), ("event", "Événements"), ("transport", "Voyager"), ("service", "Être accompagné"), ("other", "Autres")]
PRICE_CHOICES = [("", "Tous les prix"), ("free", "Gratuit"), ("paid", "Payant")]
RADIUS_CHOICES = [("", "Aucun"), ("5", "5 km"), ("10", "10 km"), ("25", "25 km"), ("50", "50 km")]
ORDERING_CHOICES = [("", "Par défaut"), ("soon", "Bientôt"), ("proximity", "Proximité")]


class OwnerDossierFormMixin:
    def configure_owner(self, user):
        self.user = user
        self.fields["dossier"].queryset = Dossier.objects.filter(owner_profile=user, owning_space__isnull=True).order_by("title")


class DiscoveryWatchCreateForm(OwnerDossierFormMixin, forms.Form):
    name = forms.CharField(label="Nom", max_length=140)
    dossier = forms.ModelChoiceField(label="Dossier", queryset=Dossier.objects.none(), required=False)
    criteria = forms.JSONField(widget=forms.HiddenInput)

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.configure_owner(user)

    def clean_criteria(self):
        return normalize_watch_criteria(self.cleaned_data["criteria"])

    def save(self):
        return DiscoveryWatch.objects.create(owner=self.user, name=self.cleaned_data["name"], dossier=self.cleaned_data.get("dossier"), criteria=self.cleaned_data["criteria"])


class DiscoveryWatchEditForm(OwnerDossierFormMixin, forms.Form):
    name = forms.CharField(label="Nom", max_length=140)
    dossier = forms.ModelChoiceField(label="Dossier", queryset=Dossier.objects.none(), required=False)
    q = forms.CharField(label="Recherche", max_length=120, required=False)
    place = forms.CharField(label="Lieu", max_length=120, required=False)
    when = forms.ChoiceField(label="Quand", choices=WHEN_CHOICES, required=False)
    period = forms.ChoiceField(label="Moment", choices=PERIOD_CHOICES, required=False)
    vertical = forms.ChoiceField(label="Type", choices=VERTICAL_CHOICES, required=False)
    price = forms.ChoiceField(label="Prix", choices=PRICE_CHOICES, required=False)
    date = forms.DateField(label="Date précise", required=False, widget=forms.DateInput(attrs={"type": "date"}))
    date_from = forms.DateField(label="Du", required=False, widget=forms.DateInput(attrs={"type": "date"}))
    date_to = forms.DateField(label="Au", required=False, widget=forms.DateInput(attrs={"type": "date"}))
    lat = forms.DecimalField(label="Latitude", required=False, max_digits=9, decimal_places=6)
    lon = forms.DecimalField(label="Longitude", required=False, max_digits=9, decimal_places=6)
    radius_km = forms.ChoiceField(label="Rayon", choices=RADIUS_CHOICES, required=False)
    ordering = forms.ChoiceField(label="Tri", choices=ORDERING_CHOICES, required=False)
    timezone = forms.CharField(label="Timezone", max_length=64, required=False)

    def __init__(self, *args, user, instance, **kwargs):
        self.instance = instance
        initial = kwargs.setdefault("initial", {})
        if not args and not kwargs.get("data"):
            initial.setdefault("name", instance.name)
            initial.setdefault("dossier", instance.dossier_id)
            for key, value in instance.criteria.items(): initial.setdefault(key, value)
        super().__init__(*args, **kwargs)
        self.configure_owner(user)

    def clean(self):
        cleaned = super().clean()
        if self.errors: return cleaned
        criteria = {}
        for key in ("q", "place", "when", "period", "vertical", "price", "date", "date_from", "date_to", "lat", "lon", "radius_km", "ordering", "timezone"):
            value = cleaned.get(key)
            if hasattr(value, "isoformat"): value = value.isoformat()
            if value not in (None, ""): criteria[key] = str(value)
        try:
            cleaned["criteria"] = normalize_watch_criteria(criteria)
        except ValidationError as exc:
            raise forms.ValidationError(exc.messages) from exc
        return cleaned

    def save(self):
        self.instance.name = self.cleaned_data["name"]
        self.instance.dossier = self.cleaned_data.get("dossier")
        self.instance.criteria = self.cleaned_data["criteria"]
        self.instance.save()
        return self.instance
