from django import forms
from django.db.models import Q

from activities.models import Activity, Occurrence
from authorization.constants import PermissionCode
from authorization.services import activity_ids_with_permission, space_ids_with_permission
from opportunities.models import Opportunity, OpportunityPublicationStatus
from organizations.models import Organization
from topics.models import ActionMatchKind, Topic

from .models import ActionNeedCandidateKind, ActionNeedIntakePolicy, ActionNeedVisibility


class ActionNeedForm(forms.Form):
    title = forms.CharField(label="Titre", max_length=220)
    description = forms.CharField(
        label="Description courte",
        max_length=600,
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )
    match_kind = forms.ChoiceField(label="Famille de contribution", choices=ActionMatchKind.choices)
    candidate_kind = forms.ChoiceField(label="Qui recherchez-vous ?", choices=ActionNeedCandidateKind.choices)
    visibility = forms.ChoiceField(label="Visibilité", choices=ActionNeedVisibility.choices)
    intake_policy = forms.ChoiceField(label="Réception des propositions", choices=ActionNeedIntakePolicy.choices)
    target_count = forms.IntegerField(label="Nombre recherché", min_value=1, required=False)
    topics = forms.ModelMultipleChoiceField(label="Topics", queryset=Topic.objects.none(), required=False)
    space = forms.ModelChoiceField(
        label="Space (laisser vide pour un besoin personnel)",
        queryset=Organization.objects.none(),
        required=False,
    )
    activity = forms.ModelChoiceField(label="Activity liée", queryset=Activity.objects.none(), required=False)
    occurrence = forms.ModelChoiceField(label="Occurrence liée", queryset=Occurrence.objects.none(), required=False)
    opportunity = forms.ModelChoiceField(label="Opportunity liée", queryset=Opportunity.objects.none(), required=False)

    def __init__(self, *args, actor, **kwargs):
        super().__init__(*args, **kwargs)
        self.actor = actor
        self.fields["topics"].queryset = Topic.objects.filter(is_active=True).order_by("label", "code")
        self.fields["opportunity"].queryset = Opportunity.objects.filter(
            publication_status=OpportunityPublicationStatus.PUBLISHED
        ).order_by("-published_at", "id")

        manageable_spaces = space_ids_with_permission(actor, PermissionCode.SPACE_MANAGE)
        manageable_activities = activity_ids_with_permission(actor, PermissionCode.ACTIVITY_MANAGE)

        if manageable_activities is None:
            activity_queryset = Activity.objects.all()
        else:
            activity_query = Q(owner_profile=actor)
            if manageable_activities:
                activity_query |= Q(pk__in=manageable_activities)
            activity_queryset = Activity.objects.filter(activity_query)
        activity_queryset = activity_queryset.select_related("space", "owner_profile").order_by("title", "id")
        self.fields["activity"].queryset = activity_queryset
        self.fields["occurrence"].queryset = Occurrence.objects.filter(activity__in=activity_queryset).select_related("activity").order_by("start_date", "start_time", "id")

        if manageable_spaces is None or manageable_activities is None:
            space_queryset = Organization.objects.all()
        else:
            space_ids = set(manageable_spaces or [])
            if manageable_activities:
                space_ids.update(
                    Activity.objects.filter(pk__in=manageable_activities)
                    .exclude(space_id=None)
                    .values_list("space_id", flat=True)
                )
            space_queryset = Organization.objects.filter(pk__in=space_ids)
        self.fields["space"].queryset = space_queryset.order_by("name", "id")

    def clean(self):
        cleaned = super().clean()
        occurrence = cleaned.get("occurrence")
        activity = cleaned.get("activity")
        if occurrence is not None and activity is None:
            self.add_error("activity", "Choisissez l'Activity de cette Occurrence.")
        elif occurrence is not None and occurrence.activity_id != activity.pk:
            self.add_error("occurrence", "L'Occurrence doit appartenir à l'Activity choisie.")
        return cleaned
