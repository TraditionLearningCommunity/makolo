from __future__ import annotations

import hashlib

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from authorization.constants import PermissionCode
from authorization.services import can
from groups.models import GroupMembership, GroupSnapshotMember
from payments.models import PaymentObligationStatus

from .contracts import AcquisitionMode, CatalogVisibility, PlanVersionStatus, RequirementPhase, SubscriptionPlanType, SubscriptionSubjectType
from .coverage_models import (
    AllocationStatus,
    CoverageStatus,
    GroupCoveragePolicy,
    SubscriptionCoverage,
    SubscriptionCoverageAllocation,
)
from .eligibility import _evaluate_requirement
from .eligibility_models import PlanRequirement
from requirements.contracts import RequirementAssessmentState
from .models import PlanVersion
from .runtime_models import Subscription


class CoverageError(ValidationError):
    pass


SETTLED = {PaymentObligationStatus.SATISFIED, PaymentObligationStatus.WAIVED}


def _identity_key(prefix, scope, key):
    key = (key or "").strip()
    if not key or len(key) > 128:
        raise CoverageError("Une clé d'idempotence non vide, de 128 caractères maximum, est requise.")
    return prefix + ":" + hashlib.sha256((str(scope) + ":" + key).encode("utf-8")).hexdigest()


def _require_payer_manager(actor, *, payer_profile=None, payer_space=None):
    if actor is None or not getattr(actor, "is_authenticated", False):
        raise PermissionDenied("Authentification requise.")
    if bool(payer_profile) == bool(payer_space):
        raise CoverageError("Le financeur doit être exactement un Profil ou un Espace.")
    if payer_profile and actor.pk != payer_profile.pk:
        raise PermissionDenied("Seul le Profil financeur contrôle son financement.")
    if payer_space and not can(actor, PermissionCode.SPACE_SUBSCRIPTION_MANAGE, space=payer_space):
        raise PermissionDenied("Mandat de gestion des abonnements de cet Espace requis.")


def _require_coverage_manager(actor, coverage):
    _require_payer_manager(actor, payer_profile=coverage.payer_profile, payer_space=coverage.payer_space)


def _require_group_manager(actor, group):
    if not can(actor, PermissionCode.GROUP_MANAGE, group=group):
        raise PermissionDenied("Autorité de gestion du Groupe requise.")


def _require_beneficiary(actor, allocation):
    if actor is None or not getattr(actor, "is_authenticated", False):
        raise PermissionDenied("Authentification requise.")
    if allocation.profile_id and allocation.profile_id != actor.pk:
        raise PermissionDenied("Seul le Profil destinataire peut accepter.")
    if allocation.space_id and not can(
        actor, PermissionCode.SPACE_SUBSCRIPTION_MANAGE, space=allocation.space
    ):
        raise PermissionDenied("Autorité sur l'Espace bénéficiaire requise.")
    if allocation.group_id:
        raise CoverageError("Un Groupe n'accepte pas de droits personnels.")


def _group_member_allowed(parent, profile):
    if parent.group_id is None or parent.status != AllocationStatus.ACTIVE:
        return False
    if parent.group.status != "active":
        return False
    if parent.group_policy == GroupCoveragePolicy.SNAPSHOT:
        return GroupSnapshotMember.objects.filter(
            snapshot_id=parent.group_snapshot_id, profile=profile,
        ).exists()
    return GroupMembership.objects.filter(
        group_id=parent.group_id, profile=profile, status="active",
    ).exists()


def _lock_beneficiary(subscription_allocation):
    if subscription_allocation.profile_id:
        target = Subscription.objects.select_for_update().filter(
            profile_id=subscription_allocation.profile_id,
        ).first()
    elif subscription_allocation.space_id:
        target = Subscription.objects.select_for_update().filter(
            space_id=subscription_allocation.space_id,
        ).first()
    else:
        raise CoverageError("Seul un bénéficiaire effectif possède une Subscription.")
    if target is None:
        raise CoverageError("Le bénéficiaire doit avoir une Subscription canonique.")
    return target


def _lock_subject(*, profile=None, space=None):
    if profile:
        return Subscription.objects.select_for_update().filter(profile=profile).first()
    return Subscription.objects.select_for_update().filter(space=space).first()


def _require_coverage_plan_eligibility(subject, version, *, at=None):
    """A purchased hidden/staff offer still enforces its acquisition Requirements."""
    from django.contrib.auth import get_user_model
    from organizations.models import Organization
    if isinstance(subject, get_user_model()):
        target_type = SubscriptionSubjectType.PROFILE
    elif isinstance(subject, Organization):
        target_type = SubscriptionSubjectType.SPACE
    else:
        raise CoverageError("Le bénéficiaire n'est pas un sujet Subscription.")
    if version.plan.subject_type != target_type:
        raise CoverageError("La formule est incompatible avec le bénéficiaire.")
    for requirement in PlanRequirement.objects.filter(
        plan_version=version, phase=RequirementPhase.ACQUISITION, is_mandatory=True,
    ):
        try:
            result = _evaluate_requirement(requirement, subject)
        except Exception as exc:
            raise CoverageError("Évaluation d'éligibilité indisponible.") from exc
        if result.state not in {
            RequirementAssessmentState.SATISFIED,
            RequirementAssessmentState.NOT_APPLICABLE,
        }:
            raise CoverageError("Les Requirements de cette formule ne sont pas satisfaits.")


@transaction.atomic
def create_coverage(
    *, actor, plan_version, payer_profile=None, payer_space=None,
    purchased_quantity, starts_at=None, ends_at=None, request_key, renewal_of=None,
):
    """Purchase a version-pinned pool; payer may differ from all beneficiaries."""
    _require_payer_manager(actor, payer_profile=payer_profile, payer_space=payer_space)
    identity = ("profile", payer_profile.pk) if payer_profile else ("space", payer_space.pk)
    key = _identity_key("coverage", identity, request_key)
    previous = SubscriptionCoverage.objects.select_for_update().filter(request_key=key).first()
    if previous:
        if (previous.plan_version_id != plan_version.pk
            or previous.purchased_quantity != purchased_quantity
            or (starts_at is not None and previous.starts_at != starts_at)
            or (ends_at is not None and previous.ends_at != ends_at)
            or previous.payer_profile_id != (payer_profile.pk if payer_profile else None)
            or previous.payer_space_id != (payer_space.pk if payer_space else None)):
            raise CoverageError("La même clé de demande a déjà été utilisée pour un autre contrat.")
        return previous
    version = PlanVersion.objects.select_related("plan").get(pk=plan_version.pk)
    try:
        terms = version.billing_terms
    except Exception as exc:
        from .billing_models import PlanVersionBillingTerms
        if not isinstance(exc, PlanVersionBillingTerms.DoesNotExist):
            raise
        raise CoverageError("Cette formule n'a pas de termes commerciaux publiés.") from exc
    if version.status != PlanVersionStatus.PUBLISHED or not version.plan.is_active:
        raise CoverageError("Seule une version publiée d'un plan actif peut être achetée.")
    if (version.catalog_visibility != CatalogVisibility.PUBLIC
        or version.acquisition_mode != AcquisitionMode.SELF_SERVICE):
        if not can(actor, PermissionCode.PLATFORM_SUBSCRIPTIONS_CATALOG_MANAGE):
            raise PermissionDenied("Cette offre ne permet pas l'acquisition libre-service.")
    if not terms.coverage_enabled:
        raise CoverageError("Cette offre ne permet pas l'achat de couvertures.")
    if purchased_quantity < 1 or purchased_quantity > terms.coverage_max_quantity:
        raise CoverageError("Quantité hors du plafond contractuel.")
    if terms.coverage_pricing_mode == "flat" and purchased_quantity != terms.coverage_max_quantity:
        raise CoverageError("Le forfait réserve exactement le nombre de places publié.")
    from .coverage_models import coverage_period_end
    starts_at = starts_at or timezone.now()
    ends_at = ends_at or coverage_period_end(
        starts_at, terms.billing_period_unit, terms.billing_period_count,
    )
    if starts_at >= ends_at:
        raise CoverageError("La période de couverture est invalide.")
    coverage = SubscriptionCoverage(
        payer_profile=payer_profile, payer_space=payer_space,
        plan_version=version, billing_terms=terms,
        purchased_quantity=purchased_quantity, starts_at=starts_at,
        ends_at=ends_at, request_key=key, created_by=actor,
        renewal_of=renewal_of,
    )
    coverage.save()
    from .billing_services import create_coverage_billing_obligation
    obligation = create_coverage_billing_obligation(
        coverage=coverage, billing_key="initial", actor=actor,
    )
    if obligation is None:
        coverage.status = CoverageStatus.ACTIVE
        coverage.state_changed_at = timezone.now()
        coverage.state_reason = "Couverture gratuite selon la version tarifaire publiée."
        coverage.save(update_fields=["status", "state_changed_at", "state_reason", "updated_at"])
    return coverage


@transaction.atomic
def reconcile_coverage_payment(*, coverage):
    """Idempotently activate a pool after all linked obligations are settled."""
    coverage = SubscriptionCoverage.objects.select_for_update().get(pk=coverage.pk)
    if coverage.status == CoverageStatus.ENDED:
        return coverage
    links = list(coverage.billing_obligation_links.select_related("obligation"))
    if not links:
        return coverage
    all_settled = all(link.obligation.status in SETTLED for link in links)
    if not all_settled and coverage.status == CoverageStatus.ACTIVE:
        coverage.status = CoverageStatus.SUSPENDED
        coverage.state_changed_at = timezone.now()
        coverage.state_reason = "Financement non réglé ; les droits financés sont suspendus."
        coverage.save(update_fields=["status", "state_changed_at", "state_reason", "updated_at"])
    elif all_settled and coverage.status == CoverageStatus.PENDING_PAYMENT:
        coverage.status = CoverageStatus.ACTIVE
        coverage.state_changed_at = timezone.now()
        coverage.state_reason = "Les obligations financières liées sont réglées."
        coverage.save(update_fields=["status", "state_changed_at", "state_reason", "updated_at"])
    return coverage


@transaction.atomic
def invite_coverage_beneficiary(
    *, actor, coverage, request_key, profile=None, space=None, group=None,
    group_parent=None, group_snapshot=None,
    group_policy=GroupCoveragePolicy.CURRENT_MEMBERS,
):
    """Create an auditable target; personal rights never arise from an invitation alone."""
    coverage = SubscriptionCoverage.objects.select_for_update(of=("self",)).select_related(
        "payer_profile", "payer_space", "plan_version__plan",
    ).get(pk=coverage.pk)
    _require_coverage_manager(actor, coverage)
    if sum((bool(profile), bool(space), bool(group))) != 1:
        raise CoverageError("Un destinataire exactement est requis.")
    if group is not None:
        _require_group_manager(actor, group)
        if group.status != "active":
            raise CoverageError("Le Groupe doit être actif.")
        if group_policy == GroupCoveragePolicy.SNAPSHOT:
            if group_snapshot is None or group_snapshot.group_id != group.pk:
                raise CoverageError("Snapshot du Groupe requis.")
        elif group_snapshot is not None:
            raise CoverageError("Un snapshot est réservé à la politique figée.")
    if group_parent is not None:
        parent = SubscriptionCoverageAllocation.objects.select_for_update().get(pk=group_parent.pk)
        _require_group_manager(actor, parent.group)
        if not profile or parent.coverage_id != coverage.pk or not _group_member_allowed(parent, profile):
            raise CoverageError("Ce Profil ne remplit pas le périmètre du Groupe.")
    key = _identity_key("allocation", coverage.pk, request_key)
    previous = coverage.allocations.filter(request_key=key).first()
    if previous:
        if (previous.profile_id != (profile.pk if profile else None)
            or previous.space_id != (space.pk if space else None)
            or previous.group_id != (group.pk if group else None)
            or previous.group_parent_id != (group_parent.pk if group_parent else None)):
            raise CoverageError("Clé d'idempotence réutilisée pour un autre bénéficiaire.")
        return previous
    duplicate = coverage.allocations.filter(
        status__in=[AllocationStatus.INVITED, AllocationStatus.ACTIVE],
    )
    if profile and duplicate.filter(profile=profile).exists():
        raise CoverageError("Ce Profil possède déjà une attribution en cours dans cette couverture.")
    if space and duplicate.filter(space=space).exists():
        raise CoverageError("Cet Espace possède déjà une attribution en cours dans cette couverture.")
    if group and duplicate.filter(group=group).exists():
        raise CoverageError("Ce Groupe délimite déjà une population dans cette couverture.")
    allocation = SubscriptionCoverageAllocation(
        coverage=coverage, profile=profile, space=space, group=group,
        group_parent=group_parent,
        group_policy=group_policy,
        group_snapshot=group_snapshot,
        status=AllocationStatus.ACTIVE if group else AllocationStatus.INVITED,
        starts_at=coverage.starts_at, ends_at=coverage.ends_at,
        request_key=key, created_by=actor,
        state_changed_at=timezone.now() if group else None,
    )
    allocation.save()
    return allocation


@transaction.atomic
def accept_coverage_allocation(*, actor, allocation, select_base=False, at=None):
    """Consent and capacity are serialized by the beneficiary and funding pool locks."""
    at = at or timezone.now()
    _require_beneficiary(actor, allocation)
    # Lock in a stable order: beneficiary Subscription before coverage, then allocation.
    target_subscription = _lock_beneficiary(allocation)
    coverage = SubscriptionCoverage.objects.select_for_update(of=("self",)).select_related(
        "plan_version__plan", "billing_terms",
    ).get(pk=allocation.coverage_id)
    allocation = SubscriptionCoverageAllocation.objects.select_for_update(of=("self",)).select_related(
        "profile", "space", "group_parent__group", "group_parent__group_snapshot",
    ).get(pk=allocation.pk)
    _require_beneficiary(actor, allocation)
    if allocation.status == AllocationStatus.ACTIVE:
        if select_base and not allocation.selected_base:
            return select_coverage_base(actor=actor, allocation=allocation, at=at)
        return allocation
    if allocation.status != AllocationStatus.INVITED:
        raise CoverageError("Cette invitation n'est plus acceptable.")
    if coverage.status != CoverageStatus.ACTIVE or not (
        coverage.starts_at <= at < coverage.ends_at
    ):
        raise CoverageError("La couverture financée n'est pas effective.")
    if not (allocation.starts_at <= at < allocation.ends_at):
        raise CoverageError("L'invitation ne se situe pas dans sa fenêtre valide.")
    if allocation.group_parent_id and not _group_member_allowed(
        allocation.group_parent, allocation.profile
    ):
        raise CoverageError("Le bénéficiaire n'est plus éligible via le Groupe.")
    subject = allocation.profile or allocation.space
    _require_coverage_plan_eligibility(subject, coverage.plan_version, at=at)
    if coverage.plan_version.plan.plan_type == SubscriptionPlanType.BASE and not select_base:
        raise CoverageError("Le remplacement de BASE demande un choix explicite du bénéficiaire.")
    occupied = coverage.allocations.filter(
        status=AllocationStatus.ACTIVE,
        group__isnull=True,
        starts_at__lte=at, ends_at__gt=at,
    ).count()
    if occupied >= coverage.purchased_quantity:
        raise CoverageError("Toutes les places financées sont déjà utilisées.")
    if select_base:
        # Multiple financed BASEs cannot be effective simultaneously.
        selected = SubscriptionCoverageAllocation.objects.select_for_update().filter(
            Q(profile_id=allocation.profile_id) if allocation.profile_id else Q(space_id=allocation.space_id),
            status=AllocationStatus.ACTIVE, selected_base=True,
        ).exclude(pk=allocation.pk)
        for old in selected:
            old.selected_base = False
            old.state_changed_at = at
            old.state_reason = "BASE remplacée par choix explicite du bénéficiaire."
            old.save(update_fields=["selected_base", "state_changed_at", "state_reason", "updated_at"])
    allocation.status = AllocationStatus.ACTIVE
    allocation.accepted_at = at
    allocation.state_changed_at = at
    allocation.state_reason = "Attribution acceptée par le bénéficiaire."
    allocation.selected_base = select_base
    allocation.selected_at = at if select_base else None
    allocation.save()
    return allocation


@transaction.atomic
def select_coverage_base(*, actor, allocation, at=None):
    at = at or timezone.now()
    _require_beneficiary(actor, allocation)
    _lock_beneficiary(allocation)
    coverage = SubscriptionCoverage.objects.select_for_update().get(pk=allocation.coverage_id)
    allocation = SubscriptionCoverageAllocation.objects.select_for_update().get(pk=allocation.pk)
    if allocation.status != AllocationStatus.ACTIVE or coverage.status != CoverageStatus.ACTIVE:
        raise CoverageError("La BASE financée doit être active.")
    if not (allocation.starts_at <= at < allocation.ends_at and coverage.starts_at <= at < coverage.ends_at):
        raise CoverageError("La BASE est en dehors de sa fenêtre effective.")
    if coverage.plan_version.plan.plan_type != SubscriptionPlanType.BASE:
        raise CoverageError("Ce bénéfice n'est pas une BASE.")
    if allocation.group_parent_id and not _group_member_allowed(allocation.group_parent, allocation.profile):
        raise CoverageError("L'appartenance au Groupe ne permet plus cette BASE.")
    _require_coverage_plan_eligibility(
        allocation.profile or allocation.space, coverage.plan_version, at=at,
    )
    if allocation.selected_base:
        return allocation
    others = SubscriptionCoverageAllocation.objects.select_for_update().filter(
        Q(profile_id=allocation.profile_id) if allocation.profile_id else Q(space_id=allocation.space_id),
        status=AllocationStatus.ACTIVE, selected_base=True,
    ).exclude(pk=allocation.pk)
    for old in others:
        old.selected_base = False
        old.state_changed_at = at
        old.state_reason = "Changement de BASE financée."
        old.save(update_fields=["selected_base", "state_changed_at", "state_reason", "updated_at"])
    allocation.selected_base = True
    allocation.selected_at = at
    allocation.state_changed_at = at
    allocation.state_reason = "BASE financée sélectionnée."
    allocation.save(update_fields=["selected_base", "selected_at", "state_changed_at", "state_reason", "updated_at"])
    return allocation


@transaction.atomic
def use_personal_base(*, actor, profile=None, space=None, at=None):
    """Opt out of financed BASE; the original Subscription BASE remains untouched."""
    if bool(profile) == bool(space):
        raise CoverageError("Un bénéficiaire Profil ou Espace est requis.")
    probe = SubscriptionCoverageAllocation(profile=profile, space=space)
    _require_beneficiary(actor, probe)
    sub = _lock_subject(profile=profile, space=space)
    if sub is None:
        raise CoverageError("Subscription du bénéficiaire introuvable.")
    selected = SubscriptionCoverageAllocation.objects.select_for_update().filter(
        Q(profile=profile) if profile else Q(space=space),
        selected_base=True, status=AllocationStatus.ACTIVE,
    )
    for allocation in selected:
        allocation.selected_base = False
        allocation.state_changed_at = at or timezone.now()
        allocation.state_reason = "Retour explicite à la BASE personnelle."
        allocation.save(update_fields=["selected_base", "state_changed_at", "state_reason", "updated_at"])


@transaction.atomic
def decide_coverage_allocation(*, actor, allocation, accept=False, reason=""):
    """Decline a pending invitation or revoke a live allocation, preserving history."""
    if accept:
        return accept_coverage_allocation(actor=actor, allocation=allocation)
    if not reason.strip():
        raise CoverageError("La décision requiert une justification.")
    coverage = SubscriptionCoverage.objects.select_for_update().get(pk=allocation.coverage_id)
    allocation = SubscriptionCoverageAllocation.objects.select_for_update().get(pk=allocation.pk)
    manager = False
    try:
        _require_coverage_manager(actor, coverage)
        manager = True
    except PermissionDenied:
        _require_beneficiary(actor, allocation)
    if allocation.group_id and not manager:
        raise PermissionDenied("La portée Groupe est gérée par le financeur autorisé.")
    if allocation.status in {AllocationStatus.REVOKED, AllocationStatus.DECLINED}:
        return allocation
    allocation.status = AllocationStatus.DECLINED if allocation.status == AllocationStatus.INVITED else AllocationStatus.REVOKED
    allocation.selected_base = False
    allocation.state_changed_at = timezone.now()
    allocation.state_reason = reason.strip()
    allocation.save(update_fields=["status", "selected_base", "state_changed_at", "state_reason", "updated_at"])
    return allocation


@transaction.atomic
def change_coverage_status(*, actor, coverage, status, reason):
    """Only the financier can suspend/resume/end its contract, never the beneficiary's own plan."""
    if status not in {CoverageStatus.SUSPENDED, CoverageStatus.ACTIVE, CoverageStatus.ENDED}:
        raise CoverageError("Transition de couverture inconnue.")
    if not (reason or "").strip():
        raise CoverageError("Une justification est requise.")
    coverage = SubscriptionCoverage.objects.select_for_update().get(pk=coverage.pk)
    _require_coverage_manager(actor, coverage)
    if coverage.status == CoverageStatus.ENDED:
        if status == CoverageStatus.ENDED:
            return coverage
        raise CoverageError("Une couverture terminée ne peut être réactivée.")
    if status == CoverageStatus.ACTIVE:
        if coverage.status != CoverageStatus.SUSPENDED:
            raise CoverageError("Seule une couverture suspendue peut reprendre.")
        links = list(coverage.billing_obligation_links.select_related("obligation"))
        if any(link.obligation.status not in SETTLED for link in links):
            raise CoverageError("Le paiement doit être régularisé avant reprise.")
        if timezone.now() >= coverage.ends_at:
            raise CoverageError("La couverture est expirée.")
    coverage.status = status
    coverage.state_reason = reason.strip()
    coverage.state_changed_at = timezone.now()
    coverage.save(update_fields=["status", "state_reason", "state_changed_at", "updated_at"])
    return coverage
