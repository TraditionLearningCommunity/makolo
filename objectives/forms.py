from django import forms
from django.contrib.auth import get_user_model
from django.db.models import Q

from authorization.constants import PermissionCode
from authorization.models import AuthorityScope, Role
from authorization.services import space_ids_with_permission
from journeys.models import Journey
from organizations.models import Organization

from .models import DossierJourneyLink, DossierLifecycle, Project, ProjectLifecycle
from .selectors import collaboration_candidates_for_dossier, dependency_candidates_for_profile, linkable_journeys_for_profile, manageable_dossiers_for_profile
from .services import ALLOWED_LIFECYCLE_TRANSITIONS, PROJECT_LIFECYCLE_TRANSITIONS, PROJECT_LINKABLE_LIFECYCLES


User = get_user_model()


def _profile_label(profile): return profile.get_full_name().strip() or profile.username


class DossierCreateForm(forms.Form):
    title = forms.CharField(label="Objectif", max_length=220)
    description = forms.CharField(label="Contexte", required=False, widget=forms.Textarea(attrs={"rows": 4}))
    owning_space = forms.ModelChoiceField(label="Espace porteur", queryset=Organization.objects.none(), required=False, help_text="Laissez vide pour un Dossier personnel.")
    deadline = forms.DateField(label="Échéance", required=False, widget=forms.DateInput(attrs={"type": "date"}))

    def __init__(self, *args, actor, **kwargs):
        super().__init__(*args, **kwargs); allowed = space_ids_with_permission(actor, PermissionCode.SPACE_MANAGE); queryset = Organization.objects.order_by("name")
        if allowed is not None: queryset = queryset.filter(pk__in=allowed)
        self.fields["owning_space"].queryset = queryset


class ProjectCreateForm(forms.Form):
    title = forms.CharField(label="Titre", max_length=220)
    description = forms.CharField(label="Contexte", required=False, widget=forms.Textarea(attrs={"rows": 4}))
    owning_space = forms.ModelChoiceField(label="Espace porteur", queryset=Organization.objects.none(), required=False, help_text="Laissez vide pour un Projet personnel.")
    starts_on = forms.DateField(label="Début", required=False, widget=forms.DateInput(attrs={"type": "date"}))
    ends_on = forms.DateField(label="Fin", required=False, widget=forms.DateInput(attrs={"type": "date"}))

    def __init__(self, *args, actor, **kwargs):
        super().__init__(*args, **kwargs); allowed = space_ids_with_permission(actor, PermissionCode.SPACE_MANAGE); queryset = Organization.objects.order_by("name")
        if allowed is not None: queryset = queryset.filter(pk__in=allowed)
        self.fields["owning_space"].queryset = queryset

    def clean(self):
        cleaned = super().clean(); starts_on = cleaned.get("starts_on"); ends_on = cleaned.get("ends_on")
        if starts_on and ends_on and starts_on > ends_on: self.add_error("ends_on", "La fin du Projet ne peut pas précéder son début.")
        return cleaned


class ProjectDossierLinkForm(forms.Form):
    dossier = forms.ModelChoiceField(label="Dossier", queryset=User.objects.none())

    def __init__(self, *args, actor, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["dossier"].queryset = manageable_dossiers_for_profile(actor).exclude(project_links__is_active=True).order_by("title")
        self.fields["dossier"].label_from_instance = lambda dossier: dossier.title


class DossierProjectForm(forms.Form):
    project = forms.ModelChoiceField(label="Projet", queryset=Project.objects.none(), required=False, help_text="Laissez vide pour retirer le Dossier de son Projet.")

    def __init__(self, *args, actor, current_project=None, **kwargs):
        super().__init__(*args, **kwargs); manage_spaces = space_ids_with_permission(actor, PermissionCode.SPACE_MANAGE); queryset = Project.objects.filter(lifecycle__in=PROJECT_LINKABLE_LIFECYCLES)
        if manage_spaces is not None: queryset = queryset.filter(Q(owner_profile=actor) | Q(owning_space_id__in=manage_spaces))
        if current_project is not None: queryset = Project.objects.filter(Q(pk=current_project.pk) | Q(pk__in=queryset.values("pk")))
        self.fields["project"].queryset = queryset.order_by("title").distinct(); self.fields["project"].initial = current_project


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
