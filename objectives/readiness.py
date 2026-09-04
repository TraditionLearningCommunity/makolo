from dataclasses import dataclass

from django.core.exceptions import PermissionDenied

from readiness import ReadinessStatus, resolve_journey_readiness

from .models import DossierLifecycle
from .selectors import active_dependencies_for_dossier, readiness_journeys_for_dossier, visible_linked_journey_ids
from .services import can_view_dossier, dependency_is_satisfied


HIDDEN_COLLECTIVE_SIGNAL = "Un élément non visible affecte actuellement l’avancement de ce dossier."
HIDDEN_DEPENDENCY_SIGNAL = "Une dépendance non visible empêche actuellement cette démarche d’avancer."


_STATUS_LABELS = {
    ReadinessStatus.BLOCKED: "Bloqué",
    ReadinessStatus.ACTION_REQUIRED: "Action requise",
    ReadinessStatus.WAITING: "En attente",
    ReadinessStatus.READY: "Prêt",
    ReadinessStatus.COMPLETE: "Terminé",
}


@dataclass(frozen=True)
class DossierNextAction:
    label: str
    url: str | None
    journey_id: object
    # Optional technical identity is server-side projection metadata. Defaults keep
    # the historical D contract source-compatible for existing callers/tests.
    key: str = ""
    source: str = ""
    source_key: str = ""
    reason_code: str = ""


@dataclass(frozen=True)
class DossierReadinessItem:
    journey_id: object
    label: str
    status: ReadinessStatus
    next_action: DossierNextAction | None = None
    hidden_dependency: bool = False

    @property
    def status_label(self):
        return _STATUS_LABELS[self.status]


@dataclass(frozen=True)
class DossierDependencyItem:
    dependent_journey_id: object
    dependent_label: str
    required_journey_id: object
    required_label: str
    is_satisfied: bool


@dataclass(frozen=True)
class DossierReadinessResult:
    dossier: object
    status: ReadinessStatus | None
    is_partial: bool
    visible_items: tuple[DossierReadinessItem, ...]
    visible_dependencies: tuple[DossierDependencyItem, ...]
    hidden_signal: str | None
    primary_next_action: DossierNextAction | None

    @property
    def status_label(self):
        return _STATUS_LABELS.get(self.status, self.dossier.get_lifecycle_display())


def _project_next_action(journey, result, *, viewer):
    action = result.next_action
    if action is None or journey.beneficiary_id != getattr(viewer, "pk", None):
        return None
    # The M1 resolver returns the exact NextAction object from one visible check.
    # Preserve that stable identity for downstream read models without exposing any
    # additional Journey or hidden dependency data.
    source_check = next((check for check in result.checks if check.next_action is action), None)
    if source_check is None:
        source_check = next((check for check in result.checks if check.next_action == action), None)
    return DossierNextAction(
        label=action.label,
        url=action.url,
        journey_id=journey.pk,
        key=action.key,
        source=action.source,
        source_key=source_check.key if source_check is not None else "",
        reason_code=source_check.reason_code if source_check is not None else "",
    )


def _collective_status(*, dossier, journey_results, unsatisfied_dependencies):
    if dossier.lifecycle == DossierLifecycle.COMPLETED:
        return ReadinessStatus.COMPLETE
    if dossier.lifecycle in {DossierLifecycle.CANCELLED, DossierLifecycle.ARCHIVED}:
        return None
    if unsatisfied_dependencies or any(result.status == ReadinessStatus.BLOCKED for result in journey_results.values()):
        return ReadinessStatus.BLOCKED
    if any(result.status == ReadinessStatus.ACTION_REQUIRED for result in journey_results.values()):
        return ReadinessStatus.ACTION_REQUIRED
    if any(result.status == ReadinessStatus.WAITING for result in journey_results.values()):
        return ReadinessStatus.WAITING
    return ReadinessStatus.READY


def resolve_dossier_readiness(dossier, *, viewer):
    """Return the privacy-safe, non-persistent Collective Readiness projection for a Dossier."""
    if not can_view_dossier(viewer, dossier):
        raise PermissionDenied("Ce Dossier n’est pas visible pour cet utilisateur.")

    if dossier.lifecycle == DossierLifecycle.COMPLETED:
        return DossierReadinessResult(dossier, ReadinessStatus.COMPLETE, False, (), (), None, None)
    if dossier.lifecycle in {DossierLifecycle.CANCELLED, DossierLifecycle.ARCHIVED}:
        return DossierReadinessResult(dossier, None, False, (), (), None, None)

    journeys = list(readiness_journeys_for_dossier(dossier))
    journey_by_id = {journey.pk: journey for journey in journeys}
    journey_results = {journey.pk: resolve_journey_readiness(journey, viewer=None) for journey in journeys}
    visible_ids = set(visible_linked_journey_ids(viewer, dossier))

    dependencies = list(active_dependencies_for_dossier(dossier))
    unsatisfied = [dependency for dependency in dependencies if not dependency_is_satisfied(dependency)]
    status = _collective_status(dossier=dossier, journey_results=journey_results, unsatisfied_dependencies=unsatisfied)

    hidden_dependency_for_visible = set()
    visible_dependencies = []
    hidden_influence = False
    dependency_action_candidates = []
    for dependency in dependencies:
        dependent_id = dependency.dependent_link.journey_id
        required_id = dependency.required_link.journey_id
        satisfied = dependency_is_satisfied(dependency)
        dependent_visible = dependent_id in visible_ids
        required_visible = required_id in visible_ids
        if dependent_visible and required_visible:
            visible_dependencies.append(
                DossierDependencyItem(
                    dependent_journey_id=dependent_id,
                    dependent_label=dependency.dependent_link.journey.activity.title,
                    required_journey_id=required_id,
                    required_label=dependency.required_link.journey.activity.title,
                    is_satisfied=satisfied,
                )
            )
        elif not satisfied:
            hidden_influence = True
            if dependent_visible and not required_visible:
                hidden_dependency_for_visible.add(dependent_id)
        if not satisfied and required_visible:
            result = journey_results.get(required_id)
            journey = journey_by_id.get(required_id)
            if result is not None and journey is not None:
                action = _project_next_action(journey, result, viewer=viewer)
                if action is not None:
                    dependency_action_candidates.append(action)

    visible_items = []
    journey_action_candidates = []
    for journey in journeys:
        result = journey_results[journey.pk]
        if journey.pk not in visible_ids:
            if (
                (status == ReadinessStatus.BLOCKED and result.status == ReadinessStatus.BLOCKED)
                or (status == ReadinessStatus.ACTION_REQUIRED and result.status == ReadinessStatus.ACTION_REQUIRED)
                or (status == ReadinessStatus.WAITING and result.status == ReadinessStatus.WAITING)
            ):
                hidden_influence = True
            continue
        action = _project_next_action(journey, result, viewer=viewer)
        if result.status == ReadinessStatus.ACTION_REQUIRED and action is not None:
            journey_action_candidates.append(action)
        if result.status in {ReadinessStatus.BLOCKED, ReadinessStatus.ACTION_REQUIRED, ReadinessStatus.WAITING} or journey.pk in hidden_dependency_for_visible:
            visible_items.append(
                DossierReadinessItem(
                    journey_id=journey.pk,
                    label=journey.activity.title,
                    status=result.status,
                    next_action=action,
                    hidden_dependency=journey.pk in hidden_dependency_for_visible,
                )
            )

    visible_items.sort(key=lambda item: str(item.journey_id))
    visible_dependencies.sort(key=lambda item: (str(item.dependent_journey_id), str(item.required_journey_id)))
    dependency_action_candidates.sort(key=lambda action: str(action.journey_id))
    journey_action_candidates.sort(key=lambda action: str(action.journey_id))
    primary_next_action = (dependency_action_candidates or journey_action_candidates or [None])[0]

    return DossierReadinessResult(
        dossier=dossier,
        status=status,
        is_partial=hidden_influence,
        visible_items=tuple(visible_items),
        visible_dependencies=tuple(visible_dependencies),
        hidden_signal=HIDDEN_COLLECTIVE_SIGNAL if hidden_influence else None,
        primary_next_action=primary_next_action,
    )
