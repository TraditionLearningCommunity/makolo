from __future__ import annotations

from dataclasses import dataclass

from django.db import models
from django.utils import timezone

from activities.models import ActivityStatus
from funding.models import FundingDetails
from funding.services import can_manage_funding
from objectives.models import DossierLifecycle, ProjectLifecycle
from objectives.readiness import resolve_owned_dossiers_readiness
from objectives.selectors import owned_dossiers_for_profile, owned_projects_for_profile
from payments.models import PaymentStatus
from payments.selectors import get_payments_visible_to
from readiness import resolve_many
from readiness.selectors import readiness_queryset
from tickets.models import TransferStatus, WaitlistStatus
from tickets.selectors import get_ticket_transfers_visible_to, get_waitlist_entries_visible_to

from core.participant_selectors import participant_active_accesses, participant_active_journeys
from core.projections import ProjectionBudget


@dataclass(frozen=True)
class PersonalOngoingEntry:
    kind: str
    value: object
    readiness: object | None = None


def build_personal_ongoing_read_model(
    profile,
    *,
    observed_at=None,
    limit=18,
    include_personal_funding=False,
):
    """Compose En cours once for Web/API while preserving owner ordering.

    This function selects and batches canonical facts. It does not rank or
    recommend. Optional Web-only families remain explicit so network contracts
    are not expanded accidentally.
    """
    observed_at = observed_at or timezone.now()
    budget = ProjectionBudget(limit=limit)
    entries = []

    journeys = list(
        readiness_queryset(
            participant_active_journeys(profile)
            .select_related(None)
            .prefetch_related(None)
            .order_by("-updated_at", "-created_at", "id")
        )[: budget.remaining]
    )
    readiness_by_id = resolve_many(journeys, viewer=profile, observed_at=observed_at)
    for journey in budget.take(journeys):
        entries.append(
            PersonalOngoingEntry(
                kind="journey",
                value=journey,
                readiness=readiness_by_id[journey.pk],
            )
        )

    if not budget.full:
        accesses = list(
            participant_active_accesses(profile, at=observed_at)
            .select_related(None)
            .prefetch_related(None)
            .select_related("activity", "occurrence")
            .prefetch_related("occurrence__place_links__place")
            .order_by("occurrence__start_date", "occurrence__start_time", "id")[
                : budget.remaining
            ]
        )
        entries.extend(
            PersonalOngoingEntry(kind="access", value=access)
            for access in budget.take(accesses)
        )

    if not budget.full:
        dossiers = list(
            owned_dossiers_for_profile(profile)
            .filter(lifecycle__in={DossierLifecycle.DRAFT, DossierLifecycle.ACTIVE})
            .order_by("-updated_at", "id")[: budget.remaining]
        )
        dossier_readiness = resolve_owned_dossiers_readiness(dossiers, viewer=profile)
        for dossier in budget.take(dossiers):
            entries.append(
                PersonalOngoingEntry(
                    kind="dossier",
                    value=dossier,
                    readiness=dossier_readiness[dossier.pk],
                )
            )

    if not budget.full:
        projects = list(
            owned_projects_for_profile(profile)
            .filter(lifecycle__in={ProjectLifecycle.DRAFT, ProjectLifecycle.ACTIVE})
            .order_by("-updated_at", "id")[: budget.remaining]
        )
        entries.extend(
            PersonalOngoingEntry(kind="project", value=project)
            for project in budget.take(projects)
        )

    if not budget.full:
        waitlist_entries = list(
            get_waitlist_entries_visible_to(profile)
            .filter(
                user=profile,
                status__in={WaitlistStatus.WAITING, WaitlistStatus.OFFERED},
            )
            .order_by("created_at", "id")[: budget.remaining]
        )
        entries.extend(
            PersonalOngoingEntry(kind="waitlist", value=entry)
            for entry in budget.take(waitlist_entries)
        )

    if not budget.full:
        transfers = list(
            get_ticket_transfers_visible_to(profile)
            .filter(status=TransferStatus.PENDING)
            .filter(models.Q(sender=profile) | models.Q(recipient=profile))
            .order_by("-created_at", "id")[: budget.remaining]
        )
        active_transfers = [transfer for transfer in transfers if transfer.is_pending_active]
        entries.extend(
            PersonalOngoingEntry(kind="transfer", value=transfer)
            for transfer in budget.take(active_transfers)
        )

    if not budget.full:
        payments = list(
            get_payments_visible_to(profile)
            .filter(
                initiated_by=profile,
                status__in={PaymentStatus.PENDING, PaymentStatus.PROCESSING},
                commerce_order__journey__isnull=True,
                obligation__journey__isnull=True,
                order__journey__isnull=True,
            )
            .order_by("-created_at", "id")[: budget.remaining]
        )
        entries.extend(
            PersonalOngoingEntry(kind="payment", value=payment)
            for payment in budget.take(payments)
        )

    if include_personal_funding and not budget.full:
        fundings = [
            funding
            for funding in FundingDetails.objects.select_related("activity")
            .filter(
                activity__owner_profile=profile,
                activity__space__isnull=True,
                activity__status__in={ActivityStatus.DRAFT, ActivityStatus.PUBLISHED},
            )
            .order_by("-activity__updated_at", "-id")[: budget.remaining]
            if can_manage_funding(profile, funding)
        ]
        entries.extend(
            PersonalOngoingEntry(kind="funding", value=funding)
            for funding in budget.take(fundings)
        )

    return tuple(entries)
