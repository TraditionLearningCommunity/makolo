from decimal import Decimal, InvalidOperation

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from activities.models import ActivityStatus, ActivityVisibility
from activities.services import create_activity, update_activity_common
from authorization.constants import PermissionCode
from authorization.services import can
from payments.models import PaymentObligationProcessingMode, PaymentObligationReason
from payments.obligation_services import create_payment_obligation

from .models import FundingContribution, FundingDetails
from .selectors import funding_accepts_contributions


def _decimal_amount(value, *, field="amount") -> Decimal:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValidationError({field: "Le montant est invalide."}) from exc
    if amount <= 0:
        raise ValidationError({field: "Le montant doit être strictement positif."})
    return amount


def can_create_space_funding(actor, space) -> bool:
    return can(actor, PermissionCode.SPACE_ACTIVITIES_MANAGE, space=space) and can(
        actor,
        PermissionCode.FINANCE_MANAGE,
        space=space,
    )


def can_manage_funding(actor, funding: FundingDetails) -> bool:
    activity = funding.activity
    if not can(actor, PermissionCode.ACTIVITY_MANAGE, activity=activity):
        return False
    if activity.space_id:
        return can(actor, PermissionCode.FINANCE_MANAGE, space=activity.space) or can(
            actor,
            PermissionCode.ACTIVITY_FINANCE_MANAGE,
            activity=activity,
        )
    return activity.owner_profile_id == getattr(actor, "pk", None)


@transaction.atomic
def create_funding(
    *,
    actor,
    title,
    short_description="",
    description="",
    space=None,
    currency="USD",
    target_amount=None,
    minimum_contribution=None,
    maximum_contribution=None,
    opens_at=None,
    closes_at=None,
    status=ActivityStatus.DRAFT,
    visibility=ActivityVisibility.PUBLIC,
):
    if not getattr(actor, "is_authenticated", False):
        raise PermissionDenied("Vous devez être connecté pour créer un financement.")
    if space is not None and not can_create_space_funding(actor, space):
        raise PermissionDenied("La création d’un financement exige les autorités Activités et Finance de cet Espace.")
    activity = create_activity(
        created_by=actor,
        title=title,
        space=space,
        owner_profile=None if space is not None else actor,
        short_description=(short_description or "").strip(),
        description=(description or "").strip(),
        status=status,
        visibility=visibility,
    )
    funding = FundingDetails(
        activity=activity,
        currency=(currency or "USD").strip().upper(),
        target_amount=target_amount,
        minimum_contribution=minimum_contribution,
        maximum_contribution=maximum_contribution,
        opens_at=opens_at,
        closes_at=closes_at,
    )
    funding.full_clean()
    funding.save()
    return funding


@transaction.atomic
def update_funding(
    *,
    actor,
    funding,
    title,
    short_description="",
    description="",
    currency="USD",
    target_amount=None,
    minimum_contribution=None,
    maximum_contribution=None,
    opens_at=None,
    closes_at=None,
    status=None,
    visibility=None,
):
    funding = (
        FundingDetails.objects.select_for_update()
        .select_related("activity")
        .get(pk=funding.pk)
    )
    if not can_manage_funding(actor, funding):
        raise PermissionDenied("Vous n’avez pas l’autorité nécessaire pour modifier ce financement.")
    activity_fields = {
        "title": title.strip(),
        "short_description": (short_description or "").strip(),
        "description": (description or "").strip(),
    }
    if status is not None:
        activity_fields["status"] = status
    if visibility is not None:
        activity_fields["visibility"] = visibility
    update_activity_common(activity=funding.activity, **activity_fields)
    funding.currency = (currency or "USD").strip().upper()
    funding.target_amount = target_amount
    funding.minimum_contribution = minimum_contribution
    funding.maximum_contribution = maximum_contribution
    funding.opens_at = opens_at
    funding.closes_at = closes_at
    funding.full_clean()
    funding.save()
    return funding


def _validate_existing_contribution(existing, *, funding, actor, amount):
    if existing.funding_id != funding.pk or existing.contributor_profile_id != actor.pk or existing.amount != amount:
        raise ValidationError("Cette référence client correspond à une autre contribution.")
    return existing


@transaction.atomic
def create_funding_contribution(*, funding, actor, amount, client_reference=""):
    if not getattr(actor, "is_authenticated", False):
        raise PermissionDenied("Vous devez être connecté pour contribuer.")
    funding = (
        FundingDetails.objects.select_for_update()
        .select_related("activity")
        .get(pk=funding.pk)
    )
    if not funding_accepts_contributions(funding, at=timezone.now()):
        raise ValidationError("Ce financement n’accepte pas de contribution actuellement.")
    amount = _decimal_amount(amount)
    reference = (client_reference or "").strip()
    if reference:
        existing = FundingContribution.objects.select_related("payment_obligation").filter(
            funding=funding,
            contributor_profile=actor,
            client_reference=reference,
        ).first()
        if existing:
            return _validate_existing_contribution(existing, funding=funding, actor=actor, amount=amount)
    contribution = FundingContribution(
        funding=funding,
        contributor_profile=actor,
        amount=amount,
        currency=funding.currency,
        client_reference=reference,
    )
    contribution.full_clean()
    try:
        contribution.save()
    except IntegrityError as exc:
        if reference:
            existing = FundingContribution.objects.select_related("payment_obligation").filter(
                funding=funding,
                contributor_profile=actor,
                client_reference=reference,
            ).first()
            if existing:
                return _validate_existing_contribution(existing, funding=funding, actor=actor, amount=amount)
        raise ValidationError("Impossible de créer cette contribution de façon unique.") from exc

    payee_space = funding.activity.space
    payee_profile = funding.activity.owner_profile if payee_space is None else None
    if payee_space is None and payee_profile is None:
        raise ValidationError("Le financement n’a pas de bénéficiaire économique canonique.")
    obligation = create_payment_obligation(
        reason=PaymentObligationReason.OTHER,
        label=f"Contribution — {funding.activity.title}",
        amount=contribution.amount,
        currency=contribution.currency,
        processing_mode=PaymentObligationProcessingMode.MAKOLO_PROVIDER,
        payer_profile=actor,
        payee_space=payee_space,
        payee_profile=payee_profile,
        due_at=funding.closes_at,
        source_key=f"funding:{contribution.pk}",
        created_by=actor,
    )
    contribution.payment_obligation = obligation
    contribution._allow_payment_link = True
    contribution.save(update_fields=["payment_obligation"])
    return contribution
