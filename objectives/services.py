from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from authorization.constants import PermissionCode
from authorization.models import AuthorityScope, Mandate
from authorization.services import can, grant_dossier_role, revoke_mandate, validate_role_for_dossier
from domain_events.contracts import DomainEventType
from domain_events.services import emit_domain_event
from journeys.models import JourneyStatus

from .models import Dossier, DossierAssignment, DossierAssignmentStatus, DossierJourneyDependency, DossierJourneyDependencyState, DossierJourneyLink, DossierLifecycle, Project, ProjectDossierLink, ProjectLifecycle


ALLOWED_LIFECYCLE_TRANSITIONS = {
    DossierLifecycle.DRAFT: {DossierLifecycle.ACTIVE, DossierLifecycle.CANCELLED, DossierLifecycle.ARCHIVED},
    DossierLifecycle.ACTIVE: {DossierLifecycle.COMPLETED, DossierLifecycle.CANCELLED, DossierLifecycle.ARCHIVED},
    DossierLifecycle.COMPLETED: {DossierLifecycle.ARCHIVED},
    DossierLifecycle.CANCELLED: {DossierLifecycle.ARCHIVED},
    DossierLifecycle.ARCHIVED: set(),
}

PROJECT_LIFECYCLE_TRANSITIONS = {
    ProjectLifecycle.DRAFT: {ProjectLifecycle.ACTIVE, ProjectLifecycle.CANCELLED, ProjectLifecycle.ARCHIVED},
    ProjectLifecycle.ACTIVE: {ProjectLifecycle.COMPLETED, ProjectLifecycle.CANCELLED, ProjectLifecycle.ARCHIVED},
    ProjectLifecycle.COMPLETED: {ProjectLifecycle.ARCHIVED},
    ProjectLifecycle.CANCELLED: {ProjectLifecycle.ARCHIVED},
    ProjectLifecycle.ARCHIVED: set(),
}
PROJECT_LINKABLE_LIFECYCLES = {ProjectLifecycle.DRAFT, ProjectLifecycle.ACTIVE}


def _require_authenticated(actor):
    if not getattr(actor, "is_authenticated", False): raise PermissionDenied("Authentification requise.")


def can_view_dossier(actor, dossier):
    if not getattr(actor, "is_authenticated", False): return False
    if can(actor, PermissionCode.PLATFORM_MANAGE): return True
    if dossier.owner_profile_id == actor.pk: return True
    if can(actor, PermissionCode.DOSSIER_VIEW, dossier=dossier): return True
    if dossier.owning_space_id:
        return can(actor, PermissionCode.SPACE_VIEW, space=dossier.owning_space) or can(actor, PermissionCode.SPACE_MANAGE, space=dossier.owning_space)
    return False


def can_manage_dossier(actor, dossier):
    if not getattr(actor, "is_authenticated", False): return False
    if can(actor, PermissionCode.PLATFORM_MANAGE): return True
    if dossier.owner_profile_id == actor.pk: return True
    if can(actor, PermissionCode.DOSSIER_MANAGE, dossier=dossier): return True
    return bool(dossier.owning_space_id and can(actor, PermissionCode.SPACE_MANAGE, space=dossier.owning_space))


def can_manage_dossier_authority(actor, dossier):
    if not getattr(actor, "is_authenticated", False): return False
    if can(actor, PermissionCode.PLATFORM_MANAGE): return True
    if dossier.owner_profile_id == actor.pk: return True
    if dossier.owning_space_id and can(actor, PermissionCode.SPACE_MANAGE, space=dossier.owning_space): return True
    return can(actor, PermissionCode.DOSSIER_AUTHORITY_MANAGE, dossier=dossier)


def can_view_project(actor, project):
    if not getattr(actor, "is_authenticated", False): return False
    if can(actor, PermissionCode.PLATFORM_MANAGE): return True
    if project.owner_profile_id == actor.pk: return True
    if project.owning_space_id:
        return can(actor, PermissionCode.SPACE_VIEW, space=project.owning_space) or can(actor, PermissionCode.SPACE_MANAGE, space=project.owning_space)
    return False


def can_manage_project(actor, project):
    if not getattr(actor, "is_authenticated", False): return False
    if can(actor, PermissionCode.PLATFORM_MANAGE): return True
    if project.owner_profile_id == actor.pk: return True
    return bool(project.owning_space_id and can(actor, PermissionCode.SPACE_MANAGE, space=project.owning_space))


def can_use_journey_for_dossier(actor, journey):
    if not getattr(actor, "is_authenticated", False): return False
    if journey.beneficiary_id == actor.pk or journey.initiated_by_id == actor.pk: return True
    return can(actor, PermissionCode.ACTIVITY_REQUESTS_VIEW, activity=journey.activity)


def dependency_is_satisfied(dependency): return dependency.required_link.journey.status == JourneyStatus.FULFILLED


def _emit(*, event_type, dossier, idempotency_key, payload, source_type="objectives.Dossier", source_id=None):
    return emit_domain_event(event_type=event_type, source_type=source_type, source_id=source_id or dossier.pk, idempotency_key=idempotency_key, space_id=dossier.owning_space_id, payload=payload)


def _emit_project(*, event_type, project, idempotency_key, payload, source_type="objectives.Project", source_id=None):
    return emit_domain_event(event_type=event_type, source_type=source_type, source_id=source_id or project.pk, idempotency_key=idempotency_key, space_id=project.owning_space_id, payload=payload)


def _dependency_payload(dependency):
    return {"dossier_id": str(dependency.dossier_id), "dependency_id": str(dependency.pk), "dependent_journey_id": str(dependency.dependent_link.journey_id), "required_journey_id": str(dependency.required_link.journey_id)}


def _locked_dossier(dossier): return Dossier.objects.select_for_update().select_related("owner_profile", "owning_space").get(pk=dossier.pk)


def _locked_project(project): return Project.objects.select_for_update().select_related("owner_profile", "owning_space").get(pk=project.pk)


def _locked_link(*, dossier, link):
    return DossierJourneyLink.objects.select_for_update().select_related("journey", "journey__activity").filter(pk=link.pk, dossier=dossier).first()


def _would_create_dependency_cycle(*, dossier, dependent_link_id, required_link_id):
    adjacency = {}
    for source_id, target_id in DossierJourneyDependency.objects.filter(dossier=dossier, state=DossierJourneyDependencyState.ACTIVE).values_list("dependent_link_id", "required_link_id"):
        adjacency.setdefault(source_id, set()).add(target_id)
    stack = [required_link_id]; visited = set()
    while stack:
        current = stack.pop()
        if current == dependent_link_id: return True
        if current in visited: continue
        visited.add(current); stack.extend(adjacency.get(current, ()))
    return False


def _require_dependency_authority(actor, dossier, dependency):
    if not can_manage_dossier(actor, dossier): raise PermissionDenied("Autorité de gestion du Dossier requise.")
    if not can_use_journey_for_dossier(actor, dependency.dependent_link.journey) or not can_use_journey_for_dossier(actor, dependency.required_link.journey):
        raise PermissionDenied("Cette dépendance n’est pas autorisée dans ce contexte.")


def _require_project_link_authority(actor, project, dossier):
    if not can_manage_project(actor, project): raise PermissionDenied("Autorité de gestion du Projet requise.")
    if not can_manage_dossier(actor, dossier): raise PermissionDenied("Autorité de gestion du Dossier requise.")


@transaction.atomic
def create_dossier(*, actor, title, description="", owner_profile=None, owning_space=None, deadline=None):
    _require_authenticated(actor)
    if bool(owner_profile) == bool(owning_space): raise ValidationError("Choisissez exactement un porteur personnel ou Espace.")
    if owner_profile is not None:
        if owner_profile.pk != actor.pk and not can(actor, PermissionCode.PLATFORM_MANAGE): raise PermissionDenied("Un Dossier personnel doit être créé pour soi-même.")
    elif not can(actor, PermissionCode.SPACE_MANAGE, space=owning_space): raise PermissionDenied("Autorité de gestion de l’Espace requise.")
    dossier = Dossier(title=title, description=description, created_by=actor, owner_profile=owner_profile, owning_space=owning_space, deadline=deadline); dossier.save()
    _emit(event_type=DomainEventType.DOSSIER_CREATED, dossier=dossier, idempotency_key=f"dossier:{dossier.pk}:created", payload={"dossier_id": str(dossier.pk), "owning_space_id": str(dossier.owning_space_id or "")})
    return dossier


@transaction.atomic
def create_project(*, actor, title, description="", owner_profile=None, owning_space=None, starts_on=None, ends_on=None):
    _require_authenticated(actor)
    if bool(owner_profile) == bool(owning_space): raise ValidationError("Choisissez exactement un porteur personnel ou Espace.")
    if owner_profile is not None:
        if owner_profile.pk != actor.pk and not can(actor, PermissionCode.PLATFORM_MANAGE): raise PermissionDenied("Un Projet personnel doit être créé pour soi-même.")
    elif not can(actor, PermissionCode.SPACE_MANAGE, space=owning_space): raise PermissionDenied("Autorité de gestion de l’Espace requise.")
    project = Project(title=title, description=description, created_by=actor, owner_profile=owner_profile, owning_space=owning_space, starts_on=starts_on, ends_on=ends_on)
    project.save()
    payload = {"project_id": str(project.pk)}
    if project.owning_space_id: payload["owning_space_id"] = str(project.owning_space_id)
    _emit_project(event_type=DomainEventType.PROJECT_CREATED, project=project, idempotency_key=f"project:{project.pk}:created", payload=payload)
    return project


@transaction.atomic
def grant_dossier_authority(*, actor, dossier, profile, role, valid_from=None, valid_until=None):
    _require_authenticated(actor); dossier = _locked_dossier(dossier)
    if not can_manage_dossier_authority(actor, dossier): raise PermissionDenied("Autorité d’administration des accès du Dossier requise.")
    if not getattr(profile, "is_active", False): raise ValidationError("Le collaborateur doit disposer d’un compte Makolo actif.")
    if not isinstance(role, str): validate_role_for_dossier(role)
    return grant_dossier_role(profile=profile, dossier=dossier, role=role, granted_by=actor, source="objectives-service", valid_from=valid_from, valid_until=valid_until)


@transaction.atomic
def revoke_dossier_authority(*, actor, dossier, mandate):
    _require_authenticated(actor); dossier = _locked_dossier(dossier)
    if not can_manage_dossier_authority(actor, dossier): raise PermissionDenied("Autorité d’administration des accès du Dossier requise.")
    mandate = Mandate.objects.select_for_update().select_related("role", "dossier").filter(pk=mandate.pk).first()
    if mandate is None or mandate.scope_type != AuthorityScope.DOSSIER or mandate.dossier_id != dossier.pk: raise ValidationError("Ce Mandat n’appartient pas à ce Dossier.")
    return revoke_mandate(mandate=mandate, actor=actor)


@transaction.atomic
def assign_dossier(*, actor, dossier, assignee):
    _require_authenticated(actor); dossier = _locked_dossier(dossier)
    if not can_manage_dossier(actor, dossier): raise PermissionDenied("Autorité de gestion du Dossier requise.")
    if not getattr(assignee, "is_active", False): raise ValidationError("Le responsable doit disposer d’un compte Makolo actif.")
    if not can_manage_dossier(assignee, dossier): raise ValidationError("Accordez d’abord une autorité de gestion du Dossier à cette personne.")
    if DossierAssignment.objects.filter(dossier=dossier, assignee=assignee, status=DossierAssignmentStatus.ACTIVE).exists(): raise ValidationError("Cette personne porte déjà la coordination de ce Dossier.")
    assignment = DossierAssignment(dossier=dossier, assignee=assignee, assigned_by=actor)
    try: assignment.save()
    except IntegrityError as exc: raise ValidationError("Cette personne porte déjà la coordination de ce Dossier.") from exc
    _emit(event_type=DomainEventType.DOSSIER_ASSIGNMENT_ADDED, dossier=dossier, source_type="objectives.DossierAssignment", source_id=assignment.pk, idempotency_key=f"dossier-assignment:{assignment.pk}:added", payload={"dossier_id": str(dossier.pk), "assignment_id": str(assignment.pk), "assignee_profile_id": str(assignee.pk)})
    return assignment


@transaction.atomic
def unassign_dossier(*, actor, dossier, assignment):
    _require_authenticated(actor); dossier = _locked_dossier(dossier)
    if not can_manage_dossier(actor, dossier): raise PermissionDenied("Autorité de gestion du Dossier requise.")
    assignment = DossierAssignment.objects.select_for_update().filter(pk=assignment.pk, dossier=dossier).first()
    if assignment is None: raise ValidationError("Responsabilité inconnue dans ce Dossier.")
    if assignment.status != DossierAssignmentStatus.ACTIVE: return assignment
    assignment.status = DossierAssignmentStatus.REMOVED; assignment.removed_by = actor; assignment.removed_at = timezone.now(); assignment._allow_status_transition = True
    assignment.save(update_fields=["status", "removed_by", "removed_at", "updated_at"])
    _emit(event_type=DomainEventType.DOSSIER_ASSIGNMENT_REMOVED, dossier=dossier, source_type="objectives.DossierAssignment", source_id=assignment.pk, idempotency_key=f"dossier-assignment:{assignment.pk}:removed", payload={"dossier_id": str(dossier.pk), "assignment_id": str(assignment.pk), "assignee_profile_id": str(assignment.assignee_id)})
    return assignment


@transaction.atomic
def link_journey(*, actor, dossier, journey):
    _require_authenticated(actor); dossier = _locked_dossier(dossier)
    if not can_manage_dossier(actor, dossier): raise PermissionDenied("Autorité de gestion du Dossier requise.")
    if not can_use_journey_for_dossier(actor, journey): raise PermissionDenied("Cette démarche n’est pas autorisée dans ce contexte.")
    existing = DossierJourneyLink.objects.select_for_update().filter(dossier=dossier, journey=journey, is_active=True).first()
    if existing: return existing
    link = DossierJourneyLink.objects.create(dossier=dossier, journey=journey, linked_by=actor)
    _emit(event_type=DomainEventType.DOSSIER_JOURNEY_LINKED, dossier=dossier, idempotency_key=f"dossier-link:{link.pk}:linked", payload={"dossier_id": str(dossier.pk), "journey_id": str(journey.pk)})
    return link


@transaction.atomic
def add_dependency(*, actor, dossier, dependent_link, required_link):
    _require_authenticated(actor); dossier = _locked_dossier(dossier)
    if not can_manage_dossier(actor, dossier): raise PermissionDenied("Autorité de gestion du Dossier requise.")
    dependent_link = _locked_link(dossier=dossier, link=dependent_link); required_link = _locked_link(dossier=dossier, link=required_link)
    if dependent_link is None or required_link is None: raise ValidationError("Les deux démarches doivent appartenir au même Dossier.")
    if not dependent_link.is_active or not required_link.is_active: raise ValidationError("Les deux démarches doivent être activement liées au Dossier.")
    if dependent_link.pk == required_link.pk: raise ValidationError("Une démarche ne peut pas dépendre d’elle-même.")
    if not can_use_journey_for_dossier(actor, dependent_link.journey) or not can_use_journey_for_dossier(actor, required_link.journey): raise PermissionDenied("Cette dépendance n’est pas autorisée dans ce contexte.")
    if DossierJourneyDependency.objects.filter(dossier=dossier, dependent_link=dependent_link, required_link=required_link, state=DossierJourneyDependencyState.ACTIVE).exists(): raise ValidationError("Cette dépendance active existe déjà.")
    if _would_create_dependency_cycle(dossier=dossier, dependent_link_id=dependent_link.pk, required_link_id=required_link.pk): raise ValidationError("Cette dépendance créerait un cycle entre les démarches du Dossier.")
    try: dependency = DossierJourneyDependency.objects.create(dossier=dossier, dependent_link=dependent_link, required_link=required_link, created_by=actor)
    except IntegrityError as exc: raise ValidationError("Cette dépendance active existe déjà.") from exc
    _emit(event_type=DomainEventType.DOSSIER_JOURNEY_DEPENDENCY_ADDED, dossier=dossier, idempotency_key=f"dossier-dependency:{dependency.pk}:added", payload=_dependency_payload(dependency)); return dependency


@transaction.atomic
def remove_dependency(*, actor, dossier, dependency):
    _require_authenticated(actor); dossier = _locked_dossier(dossier)
    dependency = DossierJourneyDependency.objects.select_for_update().select_related("dependent_link__journey__activity", "required_link__journey__activity").filter(pk=dependency.pk, dossier=dossier).first()
    if dependency is None: raise ValidationError("Dépendance inconnue dans ce Dossier.")
    _require_dependency_authority(actor, dossier, dependency)
    if dependency.state != DossierJourneyDependencyState.ACTIVE: raise ValidationError("Seule une dépendance active peut être retirée.")
    dependency.state = DossierJourneyDependencyState.REMOVED; dependency.closed_by = actor; dependency.closed_at = timezone.now(); dependency.waiver_reason = ""
    dependency.save(update_fields=["state", "closed_by", "closed_at", "waiver_reason"])
    _emit(event_type=DomainEventType.DOSSIER_JOURNEY_DEPENDENCY_REMOVED, dossier=dossier, idempotency_key=f"dossier-dependency:{dependency.pk}:removed", payload=_dependency_payload(dependency)); return dependency


@transaction.atomic
def waive_dependency(*, actor, dossier, dependency, reason):
    _require_authenticated(actor); reason = (reason or "").strip()
    if not reason: raise ValidationError("Une raison est requise pour lever ce prérequis.")
    if len(reason) > 280: raise ValidationError("La raison du waiver est trop longue.")
    dossier = _locked_dossier(dossier)
    dependency = DossierJourneyDependency.objects.select_for_update().select_related("dependent_link__journey__activity", "required_link__journey__activity").filter(pk=dependency.pk, dossier=dossier).first()
    if dependency is None: raise ValidationError("Dépendance inconnue dans ce Dossier.")
    _require_dependency_authority(actor, dossier, dependency)
    if dependency.state != DossierJourneyDependencyState.ACTIVE: raise ValidationError("Seule une dépendance active peut être levée.")
    dependency.state = DossierJourneyDependencyState.WAIVED; dependency.closed_by = actor; dependency.closed_at = timezone.now(); dependency.waiver_reason = reason
    dependency.save(update_fields=["state", "closed_by", "closed_at", "waiver_reason"])
    _emit(event_type=DomainEventType.DOSSIER_JOURNEY_DEPENDENCY_WAIVED, dossier=dossier, idempotency_key=f"dossier-dependency:{dependency.pk}:waived", payload=_dependency_payload(dependency)); return dependency


@transaction.atomic
def unlink_journey(*, actor, dossier, journey):
    _require_authenticated(actor); dossier = _locked_dossier(dossier)
    if not can_manage_dossier(actor, dossier): raise PermissionDenied("Autorité de gestion du Dossier requise.")
    if not can_use_journey_for_dossier(actor, journey): raise PermissionDenied("Cette démarche n’est pas autorisée dans ce contexte.")
    link = DossierJourneyLink.objects.select_for_update().filter(dossier=dossier, journey=journey, is_active=True).first()
    if link is None: return DossierJourneyLink.objects.filter(dossier=dossier, journey=journey).order_by("-linked_at").first()
    if DossierJourneyDependency.objects.filter(dossier=dossier, state=DossierJourneyDependencyState.ACTIVE).filter(Q(dependent_link=link) | Q(required_link=link)).exists(): raise ValidationError("Retirez ou levez d’abord les prérequis actifs liés à cette démarche.")
    link.is_active = False; link.unlinked_by = actor; link.unlinked_at = timezone.now(); link.save(update_fields=["is_active", "unlinked_by", "unlinked_at"])
    _emit(event_type=DomainEventType.DOSSIER_JOURNEY_UNLINKED, dossier=dossier, idempotency_key=f"dossier-link:{link.pk}:unlinked", payload={"dossier_id": str(dossier.pk), "journey_id": str(journey.pk)}); return link


@transaction.atomic
def set_dossier_lifecycle(*, actor, dossier, lifecycle):
    _require_authenticated(actor); dossier = _locked_dossier(dossier)
    if not can_manage_dossier(actor, dossier): raise PermissionDenied("Autorité de gestion du Dossier requise.")
    lifecycle = str(lifecycle)
    if lifecycle not in DossierLifecycle.values: raise ValidationError("Lifecycle Dossier inconnu.")
    previous = dossier.lifecycle
    if previous == lifecycle: return dossier
    if lifecycle not in ALLOWED_LIFECYCLE_TRANSITIONS[previous]: raise ValidationError(f"Transition Dossier interdite: {previous} → {lifecycle}.")
    if lifecycle == DossierLifecycle.COMPLETED and DossierJourneyDependency.objects.filter(dossier=dossier, state=DossierJourneyDependencyState.ACTIVE).exclude(required_link__journey__status=JourneyStatus.FULFILLED).exists(): raise ValidationError("Le Dossier contient encore un prérequis actif non satisfait.")
    dossier.lifecycle = lifecycle; dossier._allow_lifecycle_transition = True; dossier.save(update_fields=["lifecycle", "updated_at"])
    _emit(event_type=DomainEventType.DOSSIER_LIFECYCLE_CHANGED, dossier=dossier, idempotency_key=f"dossier:{dossier.pk}:lifecycle:{previous}:{lifecycle}:{dossier.updated_at.isoformat()}", payload={"dossier_id": str(dossier.pk), "previous": previous, "current": lifecycle}); return dossier


@transaction.atomic
def link_dossier_to_project(*, actor, project, dossier):
    _require_authenticated(actor); dossier = _locked_dossier(dossier); project = _locked_project(project)
    _require_project_link_authority(actor, project, dossier)
    if project.lifecycle not in PROJECT_LINKABLE_LIFECYCLES: raise ValidationError("Ce Projet n’accepte plus de nouveaux Dossiers.")
    current = ProjectDossierLink.objects.select_for_update().filter(dossier=dossier, is_active=True).select_related("project").first()
    if current:
        if current.project_id == project.pk: return current
        raise ValidationError("Ce Dossier appartient déjà à un autre Projet actif. Utilisez le déplacement de Projet.")
    try: link = ProjectDossierLink.objects.create(project=project, dossier=dossier, linked_by=actor)
    except IntegrityError as exc: raise ValidationError("Ce Dossier appartient déjà à un Projet actif.") from exc
    _emit_project(event_type=DomainEventType.PROJECT_DOSSIER_LINKED, project=project, source_type="objectives.ProjectDossierLink", source_id=link.pk, idempotency_key=f"project-dossier-link:{link.pk}:linked", payload={"project_id": str(project.pk), "dossier_id": str(dossier.pk), "link_id": str(link.pk)})
    return link


@transaction.atomic
def unlink_dossier_from_project(*, actor, project, dossier):
    _require_authenticated(actor); dossier = _locked_dossier(dossier); project = _locked_project(project)
    _require_project_link_authority(actor, project, dossier)
    link = ProjectDossierLink.objects.select_for_update().filter(project=project, dossier=dossier, is_active=True).first()
    if link is None: return ProjectDossierLink.objects.filter(project=project, dossier=dossier).order_by("-linked_at").first()
    link.is_active = False; link.removed_by = actor; link.removed_at = timezone.now(); link.save(update_fields=["is_active", "removed_by", "removed_at"])
    _emit_project(event_type=DomainEventType.PROJECT_DOSSIER_UNLINKED, project=project, source_type="objectives.ProjectDossierLink", source_id=link.pk, idempotency_key=f"project-dossier-link:{link.pk}:unlinked", payload={"project_id": str(project.pk), "dossier_id": str(dossier.pk), "link_id": str(link.pk)})
    return link


@transaction.atomic
def move_dossier_to_project(*, actor, dossier, target_project):
    _require_authenticated(actor); dossier = _locked_dossier(dossier); target_project = _locked_project(target_project)
    if not can_manage_dossier(actor, dossier): raise PermissionDenied("Autorité de gestion du Dossier requise.")
    if not can_manage_project(actor, target_project): raise PermissionDenied("Autorité de gestion du Projet cible requise.")
    if target_project.lifecycle not in PROJECT_LINKABLE_LIFECYCLES: raise ValidationError("Le Projet cible n’accepte plus de nouveaux Dossiers.")
    current = ProjectDossierLink.objects.select_for_update().select_related("project__owner_profile", "project__owning_space").filter(dossier=dossier, is_active=True).first()
    if current and current.project_id == target_project.pk: return current
    source_project = None
    if current:
        source_project = current.project
        if not can_manage_project(actor, source_project): raise PermissionDenied("Autorité de gestion du Projet source requise.")
        current.is_active = False; current.removed_by = actor; current.removed_at = timezone.now(); current.save(update_fields=["is_active", "removed_by", "removed_at"])
    try: new_link = ProjectDossierLink.objects.create(project=target_project, dossier=dossier, linked_by=actor)
    except IntegrityError as exc: raise ValidationError("Le Dossier n’a pas pu être déplacé vers ce Projet.") from exc
    _emit_project(event_type=DomainEventType.PROJECT_DOSSIER_MOVED, project=target_project, source_type="objectives.ProjectDossierLink", source_id=new_link.pk, idempotency_key=f"project-dossier-link:{new_link.pk}:moved", payload={"dossier_id": str(dossier.pk), "source_project_id": str(source_project.pk) if source_project else "", "target_project_id": str(target_project.pk)})
    return new_link


@transaction.atomic
def set_project_lifecycle(*, actor, project, lifecycle):
    _require_authenticated(actor); project = _locked_project(project)
    if not can_manage_project(actor, project): raise PermissionDenied("Autorité de gestion du Projet requise.")
    lifecycle = str(lifecycle)
    if lifecycle not in ProjectLifecycle.values: raise ValidationError("Lifecycle Projet inconnu.")
    previous = project.lifecycle
    if previous == lifecycle: return project
    if lifecycle not in PROJECT_LIFECYCLE_TRANSITIONS[previous]: raise ValidationError(f"Transition Projet interdite: {previous} → {lifecycle}.")
    project.lifecycle = lifecycle; project._allow_lifecycle_transition = True; project.save(update_fields=["lifecycle", "updated_at"])
    _emit_project(event_type=DomainEventType.PROJECT_LIFECYCLE_CHANGED, project=project, idempotency_key=f"project:{project.pk}:lifecycle:{previous}:{lifecycle}:{project.updated_at.isoformat()}", payload={"project_id": str(project.pk), "previous": previous, "current": lifecycle})
    return project
