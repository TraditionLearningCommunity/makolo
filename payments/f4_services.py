from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q, Sum
from django.utils import timezone

from authorization.constants import PermissionCode
from authorization.services import can, has_platform_authority
from commerce.pricing import money

from .f4_models import (
    FinancialDestination,
    FinancialDestinationStatus,
    FundFlowConfiguration,
    FundFlowRecord,
    FundFlowSourceLevel,
    FundFlowStrategy,
    FundMovement,
    FundMovementType,
    Payout,
    PayoutProvider,
    PayoutStatus,
    Settlement,
    SettlementItem,
    SettlementStatus,
)
from .models import (
    FinancialAllocationLineType,
    LedgerEntry,
    PaymentObligation,
    PaymentObligationProcessingMode,
)


ZERO = Decimal("0.00")


@dataclass(frozen=True)
class ResolvedFundFlow:
    strategy: str
    source_level: str
    source_object_id: str = ""
    configuration_id: str = ""

    @property
    def platform_custody(self):
        return self.strategy == FundFlowStrategy.PLATFORM_COLLECT


def _require_space_finance(actor, space, *, permission=PermissionCode.FINANCE_MANAGE):
    if actor is None or not can(actor, permission, space):
        raise PermissionDenied("Permission Finance insuffisante pour cet Espace.")


def _require_profile_finance(actor, profile):
    if actor is None or (actor.pk != profile.pk and not has_platform_authority(actor)):
        raise PermissionDenied("Ce Profile ne peut pas gérer les finances d’un autre bénéficiaire.")


def _require_payee_finance(actor, *, payee_space=None, payee_profile=None):
    if payee_space is not None:
        _require_space_finance(actor, payee_space)
    elif payee_profile is not None:
        _require_profile_finance(actor, payee_profile)
    else:
        raise ValidationError("Un bénéficiaire canonique est requis.")


def _activity_for_offer(offer):
    return offer.activity


def resolve_fund_flow(*, offer=None, activity=None, space=None, obligation=None):
    """Resolve Offer -> Activity -> Space -> Makolo default without copying values."""
    if obligation is not None:
        if obligation.processing_mode == PaymentObligationProcessingMode.EXTERNAL:
            return ResolvedFundFlow(FundFlowStrategy.EXTERNAL, FundFlowSourceLevel.PLATFORM, "external-processing")
        if obligation.commerce_order_id:
            items = list(obligation.commerce_order.items.select_related("offer__activity__space").all())
            if items:
                resolved = [resolve_fund_flow(offer=item.offer) for item in items]
                strategies = {item.strategy for item in resolved}
                if len(strategies) != 1:
                    raise ValidationError("Une CommerceOrder ne peut pas mélanger plusieurs stratégies Fund Flow.")
                return resolved[0]
        # Non-Commerce obligations paid through Makolo rails use the platform
        # default. Subscription remains PLATFORM allocation only, so no payee payout exists.

    if offer is not None:
        config = FundFlowConfiguration.objects.filter(offer=offer).first()
        if config:
            return ResolvedFundFlow(config.strategy, FundFlowSourceLevel.OFFER, str(offer.pk), str(config.pk))
        activity = _activity_for_offer(offer)
    if activity is not None:
        config = FundFlowConfiguration.objects.filter(activity=activity).first()
        if config:
            return ResolvedFundFlow(config.strategy, FundFlowSourceLevel.ACTIVITY, str(activity.pk), str(config.pk))
        if activity.space_id:
            space = activity.space
    if space is not None:
        config = FundFlowConfiguration.objects.filter(space=space).first()
        if config:
            return ResolvedFundFlow(config.strategy, FundFlowSourceLevel.SPACE, str(space.pk), str(config.pk))
    config = FundFlowConfiguration.objects.filter(platform_default=True).first()
    if config:
        return ResolvedFundFlow(config.strategy, FundFlowSourceLevel.PLATFORM, "platform", str(config.pk))
    # Safe operational default for new Makolo-provider obligations only. No
    # historical records are backfilled, so this never fabricates old custody.
    return ResolvedFundFlow(FundFlowStrategy.PLATFORM_COLLECT, FundFlowSourceLevel.PLATFORM, "implicit-default")


@transaction.atomic
def configure_fund_flow(*, actor, strategy, space=None, activity=None, offer=None, platform_default=False, reason=""):
    if strategy not in FundFlowStrategy.values:
        raise ValidationError("Stratégie Fund Flow inconnue.")
    scopes = int(platform_default) + int(space is not None) + int(activity is not None) + int(offer is not None)
    if scopes != 1:
        raise ValidationError("Une configuration Fund Flow cible exactement un niveau.")
    if platform_default:
        if not has_platform_authority(actor):
            raise PermissionDenied("Seul le staff plateforme autorisé peut modifier le défaut Makolo.")
        lookup = {"platform_default": True}
    elif offer is not None:
        activity = offer.activity
        if not can(actor, PermissionCode.ACTIVITY_FINANCE_MANAGE, activity=activity):
            raise PermissionDenied("Permission Activity Finance insuffisante.")
        lookup = {"offer": offer}
    elif activity is not None:
        if not can(actor, PermissionCode.ACTIVITY_FINANCE_MANAGE, activity=activity):
            raise PermissionDenied("Permission Activity Finance insuffisante.")
        lookup = {"activity": activity}
    else:
        _require_space_finance(actor, space)
        lookup = {"space": space}
    config, _ = FundFlowConfiguration.objects.update_or_create(
        **lookup,
        defaults={"strategy": strategy, "configured_by": actor, "configured_at": timezone.now(), "reason": reason},
    )
    return config


def _allocation_totals(obligation):
    allocation = obligation.financial_allocation
    payee = allocation.lines.filter(line_type=FinancialAllocationLineType.PAYEE).aggregate(total=Sum("amount"))["total"] or ZERO
    platform = allocation.lines.filter(line_type=FinancialAllocationLineType.PLATFORM).aggregate(total=Sum("amount"))["total"] or ZERO
    return money(payee), money(platform)


@transaction.atomic
def recognize_obligation_fund_flow(*, obligation):
    obligation = PaymentObligation.objects.select_for_update(of=("self",)).select_related("commerce_order").get(pk=obligation.pk)
    existing = FundFlowRecord.objects.filter(obligation=obligation).first()
    if existing:
        return existing
    if not hasattr(obligation, "financial_allocation"):
        return None
    resolved = resolve_fund_flow(obligation=obligation)
    _, platform_amount = _allocation_totals(obligation)
    receivable = platform_amount if resolved.strategy in {FundFlowStrategy.DIRECT_TO_PAYEE, FundFlowStrategy.EXTERNAL} else ZERO
    try:
        return FundFlowRecord.objects.create(
            obligation=obligation,
            strategy=resolved.strategy,
            source_level=resolved.source_level,
            source_object_id=resolved.source_object_id,
            platform_custody=resolved.platform_custody,
            platform_receivable_amount=receivable,
            currency=obligation.currency,
            source_key=f"fund-flow:obligation:{obligation.pk}",
            metadata={"configuration_id": resolved.configuration_id},
        )
    except IntegrityError:
        return FundFlowRecord.objects.get(obligation=obligation)


@transaction.atomic
def record_non_platform_fund_movement(*, obligation, movement_type, amount, provider="", provider_reference="", source_key, metadata=None):
    record = recognize_obligation_fund_flow(obligation=obligation)
    if not record or record.platform_custody:
        raise ValidationError("Un mouvement direct/externe ne doit pas être enregistré pour de la custody Makolo.")
    allowed = {
        FundMovementType.DIRECT_PAYEE,
        FundMovementType.PROVIDER_SPLIT_PAYEE,
        FundMovementType.PROVIDER_SPLIT_PLATFORM,
        FundMovementType.EXTERNAL_PAYEE,
    }
    if movement_type not in allowed:
        raise ValidationError("Type de mouvement non-platform invalide.")
    amount = money(amount)
    if amount <= ZERO:
        raise ValidationError("Le mouvement doit être strictement positif.")
    movement, _ = FundMovement.objects.get_or_create(
        source_key=source_key,
        defaults={
            "movement_type": movement_type,
            "obligation": obligation,
            "amount": amount,
            "currency": obligation.currency,
            "provider": provider,
            "provider_reference": provider_reference,
            "metadata": metadata or {},
        },
    )
    return movement


@transaction.atomic
def create_financial_destination(
    *, actor, payee_space=None, payee_profile=None, destination_type, display_name,
    provider="", external_reference="", masked_label="", last_digits="", metadata=None,
    status=FinancialDestinationStatus.PENDING,
):
    _require_payee_finance(actor, payee_space=payee_space, payee_profile=payee_profile)
    return FinancialDestination.objects.create(
        payee_space=payee_space,
        payee_profile=payee_profile,
        destination_type=destination_type,
        provider=provider,
        external_reference=external_reference,
        display_name=display_name,
        masked_label=masked_label,
        last_digits=last_digits,
        metadata=metadata or {},
        status=status,
        created_by=actor,
    )


@transaction.atomic
def set_financial_destination_status(*, destination, actor, status):
    destination = FinancialDestination.objects.select_for_update().get(pk=destination.pk)
    _require_payee_finance(actor, payee_space=destination.payee_space, payee_profile=destination.payee_profile)
    if status not in FinancialDestinationStatus.values:
        raise ValidationError("Statut de destination invalide.")
    destination.status = status
    if status == FinancialDestinationStatus.DISABLED:
        destination.disabled_by = actor
        destination.disabled_at = timezone.now()
    else:
        destination.disabled_by = None
        destination.disabled_at = None
    destination.save(update_fields=["status", "disabled_by", "disabled_at", "updated_at"])
    return destination


def _payee_filter(*, payee_space=None, payee_profile=None):
    if bool(payee_space) == bool(payee_profile):
        raise ValidationError("Un bénéficiaire Space XOR Profile est requis.")
    if payee_space:
        return Q(allocation_line__beneficiary_space=payee_space)
    return Q(allocation_line__beneficiary_profile=payee_profile)


def _candidate_payable_entries(*, payee_space=None, payee_profile=None, currency, at=None):
    at = at or timezone.now()
    return (
        LedgerEntry.objects.filter(
            economic_role=FinancialAllocationLineType.PAYEE,
            currency=currency.upper(),
            occurred_at__lte=at,
            obligation__fund_flow_record__strategy=FundFlowStrategy.PLATFORM_COLLECT,
            obligation__fund_flow_record__platform_custody=True,
        )
        .filter(_payee_filter(payee_space=payee_space, payee_profile=payee_profile))
        .filter(settlement_item__isnull=True)
        .select_related("allocation_line", "obligation")
        .order_by("occurred_at", "created_at", "id")
    )


@transaction.atomic
def build_settlement(*, actor, payee_space=None, payee_profile=None, currency, at=None, reason=""):
    _require_payee_finance(actor, payee_space=payee_space, payee_profile=payee_profile)
    currency = currency.upper()
    entries = list(_candidate_payable_entries(
        payee_space=payee_space, payee_profile=payee_profile, currency=currency, at=at
    ).select_for_update())
    if not entries:
        return None
    net = money(sum((entry.amount for entry in entries), ZERO))
    if net <= ZERO:
        # Negative payable/recoverable is carried forward and offsets future positives.
        return None
    settlement = Settlement.objects.create(
        payee_space=payee_space,
        payee_profile=payee_profile,
        currency=currency,
        amount=net,
        status=SettlementStatus.DRAFT,
        available_at=at or timezone.now(),
        created_by=actor,
        reason=reason,
    )
    for entry in entries:
        try:
            SettlementItem.objects.create(
                settlement=settlement,
                ledger_entry=entry,
                allocation_line=entry.allocation_line,
                amount=entry.amount,
                currency=entry.currency,
            )
        except IntegrityError as exc:
            raise ValidationError("Une position payable a déjà été réservée par un autre Settlement.") from exc
    explained = money(sum((item.amount for item in settlement.items.all()), ZERO))
    if explained != settlement.amount:
        raise ValidationError("Le montant net du Settlement n’est pas entièrement explicable.")
    return settlement


@transaction.atomic
def mark_settlement_ready(*, settlement, actor):
    settlement = Settlement.objects.select_for_update().get(pk=settlement.pk)
    _require_payee_finance(actor, payee_space=settlement.payee_space, payee_profile=settlement.payee_profile)
    if settlement.status == SettlementStatus.READY:
        return settlement
    if settlement.status != SettlementStatus.DRAFT:
        raise ValidationError("Seul un Settlement draft peut devenir ready.")
    if money(sum((item.amount for item in settlement.items.all()), ZERO)) != settlement.amount:
        raise ValidationError("Settlement déséquilibré.")
    settlement.status = SettlementStatus.READY
    settlement.ready_at = timezone.now()
    settlement._allow_transition = True
    settlement.save(update_fields=["status", "ready_at", "updated_at"])
    return settlement


def _destination_matches_settlement(destination, settlement):
    return bool(
        (settlement.payee_space_id and destination.payee_space_id == settlement.payee_space_id)
        or (settlement.payee_profile_id and destination.payee_profile_id == settlement.payee_profile_id)
    )


@transaction.atomic
def create_payout(*, settlement, destination, actor, provider=PayoutProvider.SANDBOX, idempotency_key=None):
    settlement = Settlement.objects.select_for_update().get(pk=settlement.pk)
    destination = FinancialDestination.objects.select_for_update().get(pk=destination.pk)
    _require_payee_finance(actor, payee_space=settlement.payee_space, payee_profile=settlement.payee_profile)
    if settlement.status not in {SettlementStatus.READY, SettlementStatus.PROCESSING, SettlementStatus.FAILED}:
        raise ValidationError("Le Settlement n’est pas disponible pour un Payout.")
    if destination.status != FinancialDestinationStatus.ACTIVE:
        raise ValidationError("Une destination non active ne peut pas recevoir un nouveau Payout.")
    if not _destination_matches_settlement(destination, settlement):
        raise PermissionDenied("La destination appartient à un autre bénéficiaire.")
    if settlement.payouts.filter(status=PayoutStatus.SUCCEEDED).exists():
        raise ValidationError("Ce Settlement a déjà un Payout réussi.")
    if idempotency_key:
        existing = Payout.objects.filter(idempotency_key=idempotency_key).first()
        if existing:
            if existing.settlement_id != settlement.pk:
                raise ValidationError("Clé d’idempotence déjà utilisée pour un autre Settlement.")
            return existing
    attempt = (settlement.payouts.aggregate(max_attempt=models_max("attempt"))["max_attempt"] or 0) + 1
    payout = Payout.objects.create(
        settlement=settlement,
        destination=destination,
        attempt=attempt,
        provider=provider,
        amount=settlement.amount,
        currency=settlement.currency,
        idempotency_key=idempotency_key,
        source_key=f"payout:settlement:{settlement.pk}:attempt:{attempt}",
        created_by=actor,
    )
    if settlement.status != SettlementStatus.PROCESSING:
        settlement.status = SettlementStatus.PROCESSING
        settlement._allow_transition = True
        settlement.save(update_fields=["status", "updated_at"])
    return payout


def models_max(field):
    from django.db.models import Max
    return Max(field)


@transaction.atomic
def mark_payout_processing(*, payout, actor=None):
    payout = Payout.objects.select_for_update().get(pk=payout.pk)
    if actor is not None:
        _require_payee_finance(actor, payee_space=payout.settlement.payee_space, payee_profile=payout.settlement.payee_profile)
    if payout.status == PayoutStatus.PROCESSING:
        return payout
    if payout.status != PayoutStatus.PENDING:
        raise ValidationError("Seul un Payout pending peut passer processing.")
    payout.status = PayoutStatus.PROCESSING
    payout.processed_at = timezone.now()
    payout._allow_transition = True
    payout.save(update_fields=["status", "processed_at", "updated_at"])
    return payout


@transaction.atomic
def mark_payout_succeeded(
    *, payout, source_key, provider_reference="", provider_fee=None, provider_settled_at=None, actor=None
):
    payout = Payout.objects.select_for_update().select_related("settlement").get(pk=payout.pk)
    settlement = Settlement.objects.select_for_update().get(pk=payout.settlement_id)
    if actor is not None:
        _require_payee_finance(actor, payee_space=settlement.payee_space, payee_profile=settlement.payee_profile)
    existing = FundMovement.objects.filter(source_key=source_key).first()
    if existing:
        if existing.payout_id != payout.pk or existing.movement_type != FundMovementType.PAYOUT:
            raise ValidationError("Clé provider déjà consommée par un autre effet financier.")
        return payout
    if payout.status == PayoutStatus.SUCCEEDED:
        # A second provider event with a different key must not double recognize cash.
        return payout
    if payout.status not in {PayoutStatus.PENDING, PayoutStatus.PROCESSING}:
        raise ValidationError("Ce Payout ne peut plus être reconnu comme réussi.")
    if settlement.payouts.exclude(pk=payout.pk).filter(status=PayoutStatus.SUCCEEDED).exists():
        raise ValidationError("Un autre Payout a déjà réglé ce Settlement.")
    payout.status = PayoutStatus.SUCCEEDED
    payout.provider_reference = provider_reference or payout.provider_reference
    payout.provider_fee = money(provider_fee) if provider_fee is not None else payout.provider_fee
    payout.provider_settled_at = provider_settled_at
    payout.succeeded_at = timezone.now()
    payout._allow_transition = True
    payout.save(update_fields=[
        "status", "provider_reference", "provider_fee", "provider_settled_at", "succeeded_at", "updated_at"
    ])
    FundMovement.objects.create(
        movement_type=FundMovementType.PAYOUT,
        payout=payout,
        amount=payout.amount,
        currency=payout.currency,
        provider=payout.provider,
        provider_reference=payout.provider_reference,
        source_key=source_key,
        occurred_at=payout.succeeded_at,
        metadata={"settlement_id": str(settlement.pk), "attempt": payout.attempt},
    )
    settlement.status = SettlementStatus.SETTLED
    settlement.settled_at = payout.succeeded_at
    settlement._allow_transition = True
    settlement.save(update_fields=["status", "settled_at", "updated_at"])
    return payout


@transaction.atomic
def mark_payout_failed(*, payout, failure_code="", failure_message="", actor=None):
    payout = Payout.objects.select_for_update().select_related("settlement").get(pk=payout.pk)
    settlement = Settlement.objects.select_for_update().get(pk=payout.settlement_id)
    if actor is not None:
        _require_payee_finance(actor, payee_space=settlement.payee_space, payee_profile=settlement.payee_profile)
    if payout.status == PayoutStatus.FAILED:
        return payout
    if payout.status not in {PayoutStatus.PENDING, PayoutStatus.PROCESSING}:
        raise ValidationError("Ce Payout ne peut pas devenir failed.")
    payout.status = PayoutStatus.FAILED
    payout.failure_code = failure_code[:120]
    payout.failure_message = failure_message[:500]
    payout.failed_at = timezone.now()
    payout._allow_transition = True
    payout.save(update_fields=["status", "failure_code", "failure_message", "failed_at", "updated_at"])
    settlement.status = SettlementStatus.FAILED
    settlement.failed_at = payout.failed_at
    settlement._allow_transition = True
    settlement.save(update_fields=["status", "failed_at", "updated_at"])
    return payout


@transaction.atomic
def retry_payout(*, payout, actor, idempotency_key=None):
    payout = Payout.objects.select_for_update().select_related("settlement", "destination").get(pk=payout.pk)
    if payout.status != PayoutStatus.FAILED:
        raise ValidationError("Seul un Payout failed peut être retenté.")
    settlement = payout.settlement
    settlement.status = SettlementStatus.READY
    settlement.failed_at = None
    settlement._allow_transition = True
    settlement.save(update_fields=["status", "failed_at", "updated_at"])
    return create_payout(
        settlement=settlement,
        destination=payout.destination,
        actor=actor,
        provider=payout.provider,
        idempotency_key=idempotency_key,
    )


@transaction.atomic
def reverse_payout(*, payout, source_key, provider_reference="", actor=None):
    payout = Payout.objects.select_for_update().select_related("settlement").get(pk=payout.pk)
    if actor is not None:
        _require_payee_finance(actor, payee_space=payout.settlement.payee_space, payee_profile=payout.settlement.payee_profile)
    existing = FundMovement.objects.filter(source_key=source_key).first()
    if existing:
        return payout
    if payout.status == PayoutStatus.REVERSED:
        return payout
    if payout.status != PayoutStatus.SUCCEEDED:
        raise ValidationError("Seul un Payout réussi peut être reversé.")
    payout.status = PayoutStatus.REVERSED
    payout.reversed_at = timezone.now()
    payout._allow_transition = True
    payout.save(update_fields=["status", "reversed_at", "updated_at"])
    FundMovement.objects.create(
        movement_type=FundMovementType.PAYOUT_REVERSAL,
        payout=payout,
        amount=-payout.amount,
        currency=payout.currency,
        provider=payout.provider,
        provider_reference=provider_reference or payout.provider_reference,
        source_key=source_key,
        occurred_at=payout.reversed_at,
        metadata={"settlement_id": str(payout.settlement_id)},
    )
    # The historical Settlement remains settled: the cash reversal is a new
    # auditable fact and future economic recovery/offset is driven by ledger facts.
    return payout


def payee_finance_projection(*, payee_space=None, payee_profile=None, currency):
    currency = currency.upper()
    payee_q = _payee_filter(payee_space=payee_space, payee_profile=payee_profile)
    ledger = LedgerEntry.objects.filter(
        economic_role=FinancialAllocationLineType.PAYEE, currency=currency
    ).filter(payee_q)
    payable = money(ledger.aggregate(total=Sum("amount"))["total"] or ZERO)
    settled = money(SettlementItem.objects.filter(
        settlement__currency=currency,
        settlement__status__in=[SettlementStatus.READY, SettlementStatus.PROCESSING, SettlementStatus.SETTLED, SettlementStatus.FAILED],
        **({"settlement__payee_space": payee_space} if payee_space else {"settlement__payee_profile": payee_profile}),
    ).aggregate(total=Sum("amount"))["total"] or ZERO)
    paid = money(FundMovement.objects.filter(
        payout__settlement__currency=currency,
        payout__settlement__status=SettlementStatus.SETTLED,
        movement_type__in=[FundMovementType.PAYOUT, FundMovementType.PAYOUT_REVERSAL],
        **({"payout__settlement__payee_space": payee_space} if payee_space else {"payout__settlement__payee_profile": payee_profile}),
    ).aggregate(total=Sum("amount"))["total"] or ZERO)
    remaining = money(payable - settled)
    return {
        "currency": currency,
        "payee_payable": payable,
        "payee_settled": settled,
        "payee_paid_out": paid,
        "payee_recoverable": money(abs(remaining)) if remaining < ZERO else ZERO,
        "settleable_unreserved": remaining if remaining > ZERO else ZERO,
        "payout_pending": Payout.objects.filter(
            settlement__currency=currency,
            status__in=[PayoutStatus.PENDING, PayoutStatus.PROCESSING],
            **({"settlement__payee_space": payee_space} if payee_space else {"settlement__payee_profile": payee_profile}),
        ).count(),
        "payout_failed": Payout.objects.filter(
            settlement__currency=currency,
            status=PayoutStatus.FAILED,
            **({"settlement__payee_space": payee_space} if payee_space else {"settlement__payee_profile": payee_profile}),
        ).count(),
    }
