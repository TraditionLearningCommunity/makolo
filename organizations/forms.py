from zoneinfo import ZoneInfo

from django import forms
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils import timezone

from activities.models import Activity, ActivityStatus, Occurrence, OccurrenceStatus
from authorization.constants import (
    LEGACY_ORGANIZATION_ROLE_TO_SYSTEM_ROLE,
    STANDARD_SPACE_ROLE_CODES,
    PermissionCode,
)
from authorization.models import AuthorityScope, Role
from authorization.services import activity_ids_with_permission

from .models import Organization, OrganizationFollow


User = get_user_model()

INPUT_CLASS = (
    "w-full rounded-2xl border border-zinc-300 bg-white px-4 py-3 text-zinc-900 "
    "outline-none transition focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 "
    "dark:border-zinc-700 dark:bg-zinc-900 dark:text-white"
)
CHECKBOX_CLASS = "h-5 w-5 rounded border-zinc-300 text-indigo-600 focus:ring-indigo-500"


class OrganizationForm(forms.ModelForm):
    class Meta:
        model = Organization
        fields = [
            "name",
            "description",
            "website",
            "contact_email",
            "contact_phone",
            "country",
            "city",
            "public_profile",
        ]
        widgets = {"description": forms.Textarea(attrs={"rows": 5})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if not isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs["class"] = INPUT_CLASS


class OrganizationMemberForm(forms.Form):
    email = forms.EmailField(label="E-mail du membre")
    role = forms.ChoiceField(label="Responsabilité")

    def __init__(self, *args, **kwargs):
        # Preserve old POST values such as event_manager during the compatibility
        # window, while every newly rendered form uses canonical role codes.
        if args and args[0] is not None and "role" in args[0]:
            data = args[0].copy()
            data["role"] = LEGACY_ORGANIZATION_ROLE_TO_SYSTEM_ROLE.get(
                data.get("role"), data.get("role")
            )
            args = (data, *args[1:])
        super().__init__(*args, **kwargs)
        roles = Role.objects.filter(
            scope_type=AuthorityScope.SPACE,
            is_system=True,
            is_active=True,
            code__in=STANDARD_SPACE_ROLE_CODES,
        ).order_by("name")
        self.fields["role"].choices = [(role.code, role.name) for role in roles]
        for field in self.fields.values():
            field.widget.attrs["class"] = INPUT_CLASS


class OccurrenceChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, occurrence):
        local_start = occurrence.start_at.astimezone(ZoneInfo(occurrence.timezone))
        label = occurrence.label.strip() if occurrence.label else local_start.strftime("%d/%m/%Y · %H:%M")
        return f"{occurrence.activity.title} — {label}"


class ManualAccessGrantForm(forms.Form):
    beneficiary_email = forms.EmailField(
        label="Adresse e-mail du bénéficiaire",
        help_text="Saisissez l’adresse exacte d’un compte Makolo actif.",
    )
    activity = forms.ModelChoiceField(queryset=Activity.objects.none(), label="Activité")
    occurrence = OccurrenceChoiceField(
        queryset=Occurrence.objects.none(),
        label="Session / date",
        required=False,
        empty_label="Toute l’activité",
        help_text="Choisissez une session lorsque le droit doit être limité à une date précise.",
    )
    reason = forms.CharField(
        label="Motif interne",
        required=False,
        max_length=240,
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Facultatif. Visible uniquement dans l’audit technique de l’émission.",
    )

    def __init__(self, *args, actor, space, **kwargs):
        super().__init__(*args, **kwargs)
        self.actor = actor
        self.space = space
        allowed_ids = activity_ids_with_permission(actor, PermissionCode.ACTIVITY_ACCESS_MANAGE)
        activities = Activity.objects.filter(space=space).exclude(
            status__in={ActivityStatus.CANCELLED, ActivityStatus.COMPLETED, ActivityStatus.ARCHIVED}
        )
        if allowed_ids is not None:
            activities = activities.filter(pk__in=allowed_ids)
        activities = activities.order_by("title", "pk")
        self.fields["activity"].queryset = activities

        now = timezone.now()
        occurrences = (
            Occurrence.objects.filter(activity__in=activities)
            .exclude(status__in={OccurrenceStatus.CANCELLED, OccurrenceStatus.COMPLETED})
            .filter(Q(end_at__isnull=True) | Q(end_at__gt=now))
            .select_related("activity")
            .order_by("activity__title", "start_at", "pk")
        )
        self.fields["occurrence"].queryset = occurrences
        for field in self.fields.values():
            field.widget.attrs["class"] = INPUT_CLASS

    def clean_beneficiary_email(self):
        email = (self.cleaned_data.get("beneficiary_email") or "").strip()
        beneficiary = User.objects.filter(email__iexact=email, is_active=True).first()
        if beneficiary is None:
            raise forms.ValidationError(
                "Aucun compte Makolo actif ne correspond à cette adresse."
            )
        self.cleaned_data["beneficiary"] = beneficiary
        return email

    def clean(self):
        cleaned = super().clean()
        activity = cleaned.get("activity")
        occurrence = cleaned.get("occurrence")
        if activity is not None and occurrence is not None and occurrence.activity_id != activity.pk:
            self.add_error("occurrence", "Cette session appartient à une autre activité.")
        return cleaned


class OrganizationFollowPreferenceForm(forms.ModelForm):
    class Meta:
        model = OrganizationFollow
        fields = [
            "notify_new_events",
            "notify_announcements",
            "email_new_events",
            "email_announcements",
        ]
        labels = {
            "notify_new_events": "Nouveaux événements dans Makolo",
            "notify_announcements": "Annonces de l’organisateur dans Makolo",
            "email_new_events": "Recevoir aussi les nouveaux événements par e-mail",
            "email_announcements": "Recevoir aussi les annonces par e-mail",
        }
        help_texts = {
            "email_new_events": "Opt-in propre à cet organisateur. Le réglage global e-mail de votre compte reste prioritaire.",
            "email_announcements": "Vous pouvez suivre un organisateur sans accepter ses e-mails marketing.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = CHECKBOX_CLASS
