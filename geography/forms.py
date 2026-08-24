from django import forms

from .models import Place, SpacePlace


INPUT_CLASS = (
    "w-full rounded-2xl border border-zinc-300 bg-white px-4 py-3 text-zinc-900 "
    "outline-none transition focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 "
    "dark:border-zinc-700 dark:bg-zinc-900 dark:text-white"
)
CHECKBOX_CLASS = "h-5 w-5 rounded border-zinc-300 text-indigo-600 focus:ring-indigo-500"


class PlaceForm(forms.ModelForm):
    class Meta:
        model = Place
        fields = ["name", "address_line", "locality", "administrative_area", "postal_code", "country_code", "latitude", "longitude", "timezone", "access_instructions"]
        labels = {
            "name": "Nom du lieu", "address_line": "Adresse", "locality": "Ville / localité",
            "administrative_area": "Province / région", "postal_code": "Code postal", "country_code": "Pays",
            "latitude": "Latitude", "longitude": "Longitude", "timezone": "Fuseau horaire",
            "access_instructions": "Instructions d’accès",
        }
        help_texts = {
            "country_code": "Code pays à 2 lettres, par exemple CD ou KE.",
            "latitude": "Facultatif. À renseigner avec la longitude uniquement si les coordonnées sont fiables.",
            "longitude": "Facultatif. À renseigner avec la latitude uniquement si les coordonnées sont fiables.",
            "timezone": "Facultatif. Utilisez un fuseau reconnu, par exemple Africa/Lubumbashi.",
        }
        widgets = {
            "access_instructions": forms.Textarea(attrs={"rows": 3}),
            "latitude": forms.NumberInput(attrs={"step": "0.000001"}),
            "longitude": forms.NumberInput(attrs={"step": "0.000001"}),
            "timezone": forms.TextInput(attrs={"placeholder": "Ex. Africa/Lubumbashi"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = INPUT_CLASS


class SpacePlaceForm(forms.ModelForm):
    class Meta:
        model = SpacePlace
        fields = ["role", "public_label", "is_primary", "is_public", "is_active", "position"]
        labels = {
            "role": "Rôle du lieu", "public_label": "Nom affiché au public", "is_primary": "Lieu principal pour ce rôle",
            "is_public": "Visible par le public", "is_active": "Disponible dans cet Espace", "position": "Ordre d’affichage",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = CHECKBOX_CLASS if isinstance(field.widget, forms.CheckboxInput) else INPUT_CLASS
