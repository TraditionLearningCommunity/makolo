from django import forms
from django.contrib.auth import get_user_model
from django.db.models import Q

from authorization.models import AuthorityScope, Role
from journeys.models import Journey

from .models import DossierJourneyLink, DossierLifecycle, Project, ProjectLifecycle
from .selectors import collaboration_candidates_for_dossier, dependency_candidates_for_profile, linkable_journeys_for_profile, manageable_dossiers_for_profile, projects_for_profile
from .services import ALLOWED_LIFECYCLE_TRANSITIONS, PROJECT_LIFECYCLE_TRANSITIONS, PROJECT_LINKABLE_LIFECYCLES, can_manage_project


User = get_user_model()


def _profile_label(profile): return profile.get_full_name().strip() or profile.username


class DossierCreateForm(forms.Form):
    title = forms.CharField(label="Objectif", max_length=220)
    description = forms.CharField(
        label="Description", required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )
    deadline = forms.DateField(
        label="Échéance", required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )

    def __init__(self, *args, actor=None, **kwargs):
        # The actor is retained for call-site compatibility. Ownership is
        # resolved by the web route, never by form POST fields.
        super().__init__(*args, **kwargs)


class ProjectCreateForm(forms.Form):
    title = forms.CharField(label="Titre", max_length=220)
    description = forms.CharField(
        label="Description", required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )
    starts_on = forms.DateField(
        label="Début", required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    ends_on = forms.DateField(
        label="Fin", required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )

    def __init__(self, *args, actor=None, **kwargs):
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get("starts_on"), cleaned.get("ends_on")
        if start and end and start > end:
            self.add_error("ends_on", "La fin ne peut pas précéder le début.")
        return cleaned


class ProjectAuthorityGrantForm(forms.Form):
    email = forms.EmailField(label="Adresse e-mail Makolo exacte")
    role = forms.ModelChoiceField(
        label="Niveau d'accès",
        queryset=Role.objects.filter(
            scope_type=AuthorityScope.PROJECT,
            is_system=True, is_active=True,
        ).order_by("name"),
    )

    def clean_email(self):
        email = self.cleaned_data["email"]
        matches = list(User.objects.filter(
            email__iexact=email, is_active=True,
        ).order_by("pk")[:2])
        if len(matches) != 1:
            raise forms.ValidationError("Le compte Makolo est introuvable ou ambigu.")
        self.profile = matches[0]
        return email


class ProjectEditForm(forms.Form):
    title = forms.CharField(label="Nom du Projet", max_length=220)
    description = forms.CharField(
        label="Description", required=False,
        widget=forms.Textarea(attrs={"rows": 4}),
    )
    starts_on = forms.DateField(
        label="Début de l’horizon", required=False,
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
    )
    ends_on = forms.DateField(
        label="Fin de l’horizon", required=False,
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
    )

    def __init__(self, *args, project, **kwargs):
        super().__init__(*args, **kwargs)
        for key in ("title", "description", "starts_on", "ends_on"):
            self.fields[key].initial = getattr(project, key)

    def clean(self):
        cleaned = super().clean()
        if (cleaned.get("starts_on") and cleaned.get("ends_on") and
                cleaned["starts_on"] > cleaned["ends_on"]):
            self.add_error("ends_on", "La fin ne peut pas précéder le début.")
        return cleaned


class ProjectChildDossierForm(forms.Form):
    title = forms.CharField(label="Objectif du Dossier", max_length=220)
    description = forms.CharField(
        label="Contexte", required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )
    deadline = forms.DateField(
        label="Échéance", required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )


class ProjectDossierLinkForm(forms.Form):
    dossier = forms.ModelChoiceField(label="Dossier", queryset=User.objects.none())

    def __init__(self, *args, actor, actor_context=None, **kwargs):
        super().__init__(*args, **kwargs)
        dossiers = manageable_dossiers_for_profile(actor)
        if actor_context is not None:
            dossiers = actor_context.filter(dossiers)
        self.fields["dossier"].queryset = dossiers.exclude(
            project_links__is_active=True,
        ).order_by("title")
        self.fields["dossier"].label_from_instance = lambda dossier: dossier.title


class DossierEditForm(forms.Form):
    title = forms.CharField(label="Objectif du Dossier", max_length=220)
    description = forms.CharField(
        label="Description", required=False,
        widget=forms.Textarea(attrs={"rows": 4}),
    )
    deadline = forms.DateField(
        label="Échéance", required=False,
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
    )

    def __init__(self, *args, dossier, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("title", "description", "deadline"):
            self.fields[name].initial = getattr(dossier, name)


class DossierProjectForm(forms.Form):
    project = forms.ModelChoiceField(
        label="Projet", queryset=Project.objects.none(), required=False,
        help_text="Laissez vide pour retirer le Dossier de son Projet.",
    )

    def __init__(self, *args, actor, current_project=None,
                 actor_context=None, **kwargs):
        super().__init__(*args, **kwargs)
        eligible = projects_for_profile(actor)
        if actor_context is not None:
            eligible = actor_context.filter(eligible)
        eligible = eligible.filter(
            lifecycle__in=PROJECT_LINKABLE_LIFECYCLES,
        ).select_related("owning_space")
        ids = [row.pk for row in eligible if can_manage_project(actor, row)]
        if current_project is not None:
            ids.append(current_project.pk)
        self.fields["project"].queryset = Project.objects.filter(
            pk__in=ids,
        ).order_by("title").distinct()
        self.fields["project"].initial = current_project


class DossierJourneyLinkForm(forms.Form):
    journey = forms.ModelChoiceField(label="Démarche", queryset=Journey.objects.none())
    def __init__(self, *args, actor, dossier, **kwargs):
        super().__init__(*args, **kwargs); self.fields["journey"].queryset = linkable_journeys_for_profile(actor, dossier=dossier); self.fields["journey"].label_from_instance = lambda journey: journey.activity.title


class DossierDependencyForm(forms.Form):
    dependent_link = forms.ModelChoiceField(label="Démarche dépendante", queryset=DossierJourneyLink.objects.none())
    required_link = forms.ModelChoiceField(label="Démarche requise", queryset=DossierJourneyLink.objects.none())
    def __init__(self, *args, actor, dossier, **kwargs):
        super().__init__(*args, **kwargs); queryset = dependency_candidates_for_profile(actor, dossier); label = lambda link: link.journey.activity.title
        self.fields["dependent_link"].queryset = queryset; self.fields["required_link"].queryset = queryset; self.fields["dependent_link"].label_from_instance = label; self.fields["required_link"].label_from_instance = label


class DossierDependencyWaiverForm(forms.Form): reason = forms.CharField(label="Raison", max_length=280, widget=forms.TextInput())


class DossierLifecycleForm(forms.Form):
    lifecycle = forms.ChoiceField(label="État")
    def __init__(self, *args, dossier, **kwargs):
        super().__init__(*args, **kwargs); allowed = {dossier.lifecycle, *ALLOWED_LIFECYCLE_TRANSITIONS[dossier.lifecycle]}; self.fields["lifecycle"].choices = [(value, label) for value, label in DossierLifecycle.choices if value in allowed]; self.fields["lifecycle"].initial = dossier.lifecycle


class ProjectLifecycleForm(forms.Form):
    lifecycle = forms.ChoiceField(label="État")
    def __init__(self, *args, project, **kwargs):
        super().__init__(*args, **kwargs); allowed = {project.lifecycle, *PROJECT_LIFECYCLE_TRANSITIONS[project.lifecycle]}; self.fields["lifecycle"].choices = [(value, label) for value, label in ProjectLifecycle.choices if value in allowed]; self.fields["lifecycle"].initial = project.lifecycle


class DossierAssignmentForm(forms.Form):
    assignee = forms.ModelChoiceField(label="Responsable", queryset=User.objects.none())
    def __init__(self, *args, dossier, **kwargs):
        super().__init__(*args, **kwargs); self.fields["assignee"].queryset = collaboration_candidates_for_dossier(dossier); self.fields["assignee"].label_from_instance = _profile_label


class DossierAuthorityGrantForm(forms.Form):
    profile = forms.ModelChoiceField(label="Collaborateur", queryset=User.objects.none())
    role = forms.ModelChoiceField(label="Niveau d’accès", queryset=Role.objects.none())
    def __init__(self, *args, dossier, **kwargs):
        super().__init__(*args, **kwargs); self.fields["profile"].queryset = collaboration_candidates_for_dossier(dossier); self.fields["profile"].label_from_instance = _profile_label; self.fields["role"].queryset = Role.objects.filter(scope_type=AuthorityScope.DOSSIER, is_system=True, is_active=True).order_by("name")
