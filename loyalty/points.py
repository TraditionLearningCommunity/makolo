from decimal import Decimal, ROUND_HALF_UP

from django.db import IntegrityError, transaction
from django.utils import timezone

from access.models import AccessUse, AccessUseResult
from commerce.models import CommerceOrder, CommerceOrderStatus

from .models import (
    LedgerKind,
    LoyaltyAccount,
    LoyaltyLedgerEntry,
    LoyaltyProgram,
    MembershipStatus,
    MembershipSubscription,
)


def get_or_create_account(program, user):
    account, _ = LoyaltyAccount.objects.get_or_create(program=program, user=user)
    return account


def recalculate_tier(account):
    account = LoyaltyAccount.objects.select_for_update().select_related(
        "program", "current_tier"
    ).get(pk=account.pk)
    tier = (
        account.program.tiers.filter(
            is_active=True,
            threshold_points__lte=account.lifetime_earned,
        )
        .order_by("-threshold_points", "name")
        .first()
    )
    if account.current_tier_id != getattr(tier, "pk", None):
        account.current_tier = tier
        account.save(update_fields=["current_tier", "updated_at"])
    return account


def _membership_multiplier(program, user, now):
    subscription = (
        MembershipSubscription.objects.filter(
            program=program,
            user=user,
            status=MembershipStatus.ACTIVE,
            starts_at__lte=now,
            ends_at__gt=now,
        )
        .select_related("plan")
        .first()
    )
    return subscription.plan.points_multiplier if subscription else Decimal("1.00")


def _tier_multiplier(account):
    if account.current_tier_id and account.current_tier and account.current_tier.is_active:
        return account.current_tier.points_multiplier
    return Decimal("1.00")


def _scaled_points(base_points, account, now):
    if base_points <= 0:
        return 0
    factor = _membership_multiplier(account.program, account.user, now) * _tier_multiplier(account)
    return int((Decimal(base_points) * factor).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


@transaction.atomic
def credit_points(
    *,
    program,
    user,
    points,
    kind,
    description,
    idempotency_key,
    metadata=None,
):
    if points <= 0:
        return None
    existing = LoyaltyLedgerEntry.objects.filter(idempotency_key=idempotency_key).first()
    if existing:
        return existing
    account = get_or_create_account(program, user)
    account = LoyaltyAccount.objects.select_for_update().select_related(
        "current_tier", "program", "user"
    ).get(pk=account.pk)
    try:
        with transaction.atomic():
            entry = LoyaltyLedgerEntry.objects.create(
                account=account,
                kind=kind,
                points=points,
                description=description[:255],
                idempotency_key=idempotency_key,
                metadata=metadata or {},
            )
    except IntegrityError:
        return LoyaltyLedgerEntry.objects.get(idempotency_key=idempotency_key)
    account.points_balance += points
    account.lifetime_earned += points
    account.save(update_fields=["points_balance", "lifetime_earned", "updated_at"])
    recalculate_tier(account)
    return entry


@transaction.atomic
def award_commerce_order_points(order: CommerceOrder):
    if order.status != CommerceOrderStatus.CONFIRMED or not order.buyer_id or not order.payee_space_id:
        return None
    program = LoyaltyProgram.objects.filter(
        organization_id=order.payee_space_id,
        is_active=True,
    ).first()
    if not program:
        return None
    account = get_or_create_account(program, order.buyer)
    account = LoyaltyAccount.objects.select_related(
        "current_tier", "program", "user"
    ).get(pk=account.pk)
    quantity = sum(item.quantity for item in order.items.all())
    base = program.points_per_order + (program.points_per_ticket * quantity)
    points = _scaled_points(base, account, order.confirmed_at or timezone.now())
    return credit_points(
        program=program,
        user=order.buyer,
        points=points,
        kind=LedgerKind.ORDER,
        description=f"Commande {order.reference}",
        idempotency_key=f"commerce-order:{order.pk}",
        metadata={
            "source_type": "commerce_order",
            "commerce_order_id": str(order.pk),
            "base_points": base,
            "unit_quantity": quantity,
        },
    )


@transaction.atomic
def reverse_commerce_order_points(order: CommerceOrder):
    original = LoyaltyLedgerEntry.objects.select_related("account").filter(
        idempotency_key=f"commerce-order:{order.pk}"
    ).first()
    if not original:
        return None
    reversal_key = f"commerce-order-reversal:{order.pk}"
    existing = LoyaltyLedgerEntry.objects.filter(idempotency_key=reversal_key).first()
    if existing:
        return existing
    account = LoyaltyAccount.objects.select_for_update().get(pk=original.account_id)
    entry = LoyaltyLedgerEntry.objects.create(
        account=account,
        kind=LedgerKind.ORDER_REVERSAL,
        points=-original.points,
        description=f"Annulation {order.reference}",
        idempotency_key=reversal_key,
        metadata={
            "source_type": "commerce_order",
            "commerce_order_id": str(order.pk),
            "original_points": original.points,
        },
    )
    account.points_balance -= original.points
    account.lifetime_earned = max(account.lifetime_earned - original.points, 0)
    account.save(update_fields=["points_balance", "lifetime_earned", "updated_at"])
    recalculate_tier(account)
    return entry


@transaction.atomic
def award_access_use_points(access_use: AccessUse):
    if access_use.result != AccessUseResult.ACCEPTED:
        return None
    access = access_use.access
    if not access.beneficiary_id or not access.activity.space_id:
        return None
    program = LoyaltyProgram.objects.filter(
        organization_id=access.activity.space_id,
        is_active=True,
    ).first()
    if not program or program.points_per_checkin <= 0:
        return None
    account = get_or_create_account(program, access.beneficiary)
    account = LoyaltyAccount.objects.select_related(
        "current_tier", "program", "user"
    ).get(pk=account.pk)
    points = _scaled_points(program.points_per_checkin, account, access_use.used_at)
    return credit_points(
        program=program,
        user=access.beneficiary,
        points=points,
        kind=LedgerKind.CHECKIN,
        description=f"Présence — {access.activity.title}",
        idempotency_key=f"access-use:{access_use.pk}",
        metadata={
            "source_type": "access_use",
            "access_use_id": str(access_use.pk),
            "access_id": str(access.pk),
        },
    )
