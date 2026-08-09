import uuid
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from notifications.models import NotificationCategory, NotificationKind
from notifications.services import create_notification
from promotions.models import PromotionCode
from tickets.models import TicketOrderStatus, TicketStatus

from .models import (
    LedgerKind,
    LoyaltyAccount,
    LoyaltyLedgerEntry,
    LoyaltyProgram,
    LoyaltyReward,
    LoyaltyRewardRedemption,
    MembershipPlan,
    MembershipStatus,
    MembershipSubscription,
)
from .permissions import user_can_manage_loyalty_finance, user_can_manage_loyalty_strategy


def _notify(user, *, title, message, dedup_key, organization_id):
    if not user:
        return
    create_notification(
        recipient=user,
        kind=NotificationKind.SYSTEM,
        category=NotificationCategory.SYSTEM,
        title=title,
        message=message,
        action_url="/loyalty/",
        dedup_key=dedup_key,
        metadata={"organization_id": str(organization_id)},
    )


def get_or_create_account(program, user):
    account, _ = LoyaltyAccount.objects.get_or_create(program=program, user=user)
    return account


def recalculate_tier(account):
    account = LoyaltyAccount.objects.select_for_update().select_related("program", "current_tier").get(pk=account.pk)
    tier = (
        account.program.tiers.filter(is_active=True, threshold_points__lte=account.lifetime_earned)
        .order_by("-threshold_points", "name")
        .first()
    )
    old_id = account.current_tier_id
    if old_id != getattr(tier, "pk", None):
        account.current_tier = tier
        account.save(update_fields=["current_tier", "updated_at"])
        if tier and old_id:
            transaction.on_commit(
                lambda: _notify(
                    account.user,
                    title=f"Nouveau niveau : {tier.name}",
                    message=f"Votre fidélité chez {account.program.organization.name} atteint le niveau {tier.name}.",
                    dedup_key=f"loyalty-tier:{account.pk}:{tier.pk}",
                    organization_id=account.program.organization_id,
                )
            )
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
def _credit_points(*, program, user, points, kind, description, idempotency_key, order=None, ticket=None, subscription=None, reward_redemption=None, created_by=None, metadata=None):
    if points <= 0:
        return None
    existing = LoyaltyLedgerEntry.objects.filter(idempotency_key=idempotency_key).first()
    if existing:
        return existing
    account = get_or_create_account(program, user)
    account = LoyaltyAccount.objects.select_for_update().select_related("current_tier", "program", "user").get(pk=account.pk)
    try:
        entry = LoyaltyLedgerEntry.objects.create(
            account=account,
            kind=kind,
            points=points,
            description=description[:255],
            idempotency_key=idempotency_key,
            order=order,
            ticket=ticket,
            subscription=subscription,
            reward_redemption=reward_redemption,
            created_by=created_by,
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
def _debit_points(*, account, points, kind, description, idempotency_key, reward_redemption=None, created_by=None):
    if points <= 0:
        raise ValidationError("Le nombre de points doit être positif.")
    existing = LoyaltyLedgerEntry.objects.filter(idempotency_key=idempotency_key).first()
    if existing:
        return existing
    account = LoyaltyAccount.objects.select_for_update().get(pk=account.pk)
    if account.points_balance < points:
        raise ValidationError("Solde de points insuffisant.")
    entry = LoyaltyLedgerEntry.objects.create(
        account=account,
        kind=kind,
        points=-points,
        description=description[:255],
        idempotency_key=idempotency_key,
        reward_redemption=reward_redemption,
        created_by=created_by,
    )
    account.points_balance -= points
    account.lifetime_redeemed += points
    account.save(update_fields=["points_balance", "lifetime_redeemed", "updated_at"])
    return entry


@transaction.atomic
def award_order_points(order):
    if order.status != TicketOrderStatus.CONFIRMED or not order.buyer_id or not order.event.organization_id:
        return None
    program = LoyaltyProgram.objects.filter(organization_id=order.event.organization_id, is_active=True).first()
    if not program:
        return None
    account = get_or_create_account(program, order.buyer)
    account = LoyaltyAccount.objects.select_related("current_tier", "program", "user").get(pk=account.pk)
    quantity = sum(item.quantity for item in order.items.all())
    base = program.points_per_order + (program.points_per_ticket * quantity)
    points = _scaled_points(base, account, order.confirmed_at or timezone.now())
    return _credit_points(
        program=program,
        user=order.buyer,
        points=points,
        kind=LedgerKind.ORDER,
        description=f"Commande {order.reference}",
        idempotency_key=f"order:{order.pk}",
        order=order,
        metadata={"base_points": base, "ticket_quantity": quantity},
    )


@transaction.atomic
def reverse_order_points(order):
    original = LoyaltyLedgerEntry.objects.select_related("account").filter(idempotency_key=f"order:{order.pk}").first()
    if not original:
        return None
    reversal_key = f"order-reversal:{order.pk}"
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
        order=order,
        metadata={"original_points": original.points},
    )
    account.points_balance -= original.points
    account.lifetime_earned = max(account.lifetime_earned - original.points, 0)
    account.save(update_fields=["points_balance", "lifetime_earned", "updated_at"])
    recalculate_tier(account)
    return entry


@transaction.atomic
def award_checkin_points(ticket):
    if ticket.status != TicketStatus.USED or not ticket.owner_id or not ticket.event.organization_id:
        return None
    program = LoyaltyProgram.objects.filter(organization_id=ticket.event.organization_id, is_active=True).first()
    if not program or program.points_per_checkin <= 0:
        return None
    account = get_or_create_account(program, ticket.owner)
    account = LoyaltyAccount.objects.select_related("current_tier", "program", "user").get(pk=account.pk)
    points = _scaled_points(program.points_per_checkin, account, ticket.used_at or timezone.now())
    return _credit_points(
        program=program,
        user=ticket.owner,
        points=points,
        kind=LedgerKind.CHECKIN,
        description=f"Check-in {ticket.event.title}",
        idempotency_key=f"checkin:{ticket.pk}",
        ticket=ticket,
    )


def _private_code(prefix):
    return f"{prefix}{uuid.uuid4().hex[:16].upper()}"


def _create_private_benefit_code(*, promotion, created_by, starts_at, ends_at, prefix):
    if not promotion:
        return None
    for _ in range(5):
        code = PromotionCode(
            promotion=promotion,
            code=_private_code(prefix),
            label="Avantage fidélité Makolo",
            starts_at=starts_at,
            ends_at=ends_at,
            max_redemptions=1,
            is_private=True,
            is_active=True,
            created_by=created_by,
        )
        try:
            code.full_clean()
            code.save()
            return code
        except IntegrityError:
            continue
    raise ValidationError("Impossible de générer un code avantage unique.")


@transaction.atomic
def request_membership(*, user, plan):
    if not getattr(user, "is_authenticated", False):
        raise PermissionDenied("Connectez-vous pour rejoindre ce membership.")
    plan = MembershipPlan.objects.select_for_update().select_related("program", "program__organization").get(pk=plan.pk)
    if not plan.is_active or not plan.program.is_active:
        raise ValidationError("Ce membership n'est pas disponible.")
    current = MembershipSubscription.objects.filter(
        program=plan.program,
        user=user,
        status__in=[MembershipStatus.PENDING, MembershipStatus.ACTIVE],
    ).first()
    if current:
        return current
    subscription = MembershipSubscription.objects.create(
        program=plan.program,
        plan=plan,
        user=user,
        price_amount=plan.price,
        currency=plan.currency,
    )
    if plan.is_free:
        return activate_membership(subscription=subscription, actor=user, free_self_activation=True)
    return subscription


@transaction.atomic
def activate_membership(*, subscription, actor, free_self_activation=False):
    subscription = MembershipSubscription.objects.select_for_update().select_related(
        "program", "program__organization", "plan", "plan__benefit_promotion", "user"
    ).get(pk=subscription.pk)
    if subscription.status == MembershipStatus.ACTIVE:
        return subscription
    if subscription.status != MembershipStatus.PENDING:
        raise ValidationError("Seule une adhésion en attente peut être activée.")
    if free_self_activation:
        if subscription.price_amount != 0 or actor.pk != subscription.user_id:
            raise PermissionDenied("Activation gratuite invalide.")
        source = "free"
    else:
        if not user_can_manage_loyalty_finance(actor, subscription.program.organization):
            raise PermissionDenied("Un rôle Finance, Owner ou Admin est requis pour activer un membership payant.")
        source = "manual"
    now = timezone.now()
    subscription.status = MembershipStatus.ACTIVE
    subscription.starts_at = now
    subscription.ends_at = now + timedelta(days=subscription.plan.duration_days)
    subscription.activated_at = now
    subscription.activated_by = actor
    subscription.activation_source = source
    if subscription.plan.benefit_promotion_id:
        subscription.benefit_code = _create_private_benefit_code(
            promotion=subscription.plan.benefit_promotion,
            created_by=subscription.plan.created_by,
            starts_at=now,
            ends_at=subscription.ends_at,
            prefix="MEM",
        )
    subscription.save(update_fields=[
        "status", "starts_at", "ends_at", "activated_at", "activated_by",
        "activation_source", "benefit_code", "updated_at",
    ])
    get_or_create_account(subscription.program, subscription.user)
    if subscription.plan.join_bonus_points:
        _credit_points(
            program=subscription.program,
            user=subscription.user,
            points=subscription.plan.join_bonus_points,
            kind=LedgerKind.MEMBERSHIP_BONUS,
            description=f"Bonus membership {subscription.plan.name}",
            idempotency_key=f"membership-bonus:{subscription.plan_id}:{subscription.user_id}",
            subscription=subscription,
        )
    transaction.on_commit(
        lambda: _notify(
            subscription.user,
            title=f"Membership actif — {subscription.plan.name}",
            message=f"Votre membership {subscription.program.organization.name} est maintenant actif.",
            dedup_key=f"membership-active:{subscription.pk}",
            organization_id=subscription.program.organization_id,
        )
    )
    return subscription


@transaction.atomic
def cancel_membership(*, subscription, actor):
    subscription = MembershipSubscription.objects.select_for_update().select_related("program__organization", "user", "benefit_code").get(pk=subscription.pk)
    is_owner = getattr(actor, "is_authenticated", False) and actor.pk == subscription.user_id
    if not is_owner and not user_can_manage_loyalty_finance(actor, subscription.program.organization):
        raise PermissionDenied("Vous ne pouvez pas annuler cette adhésion.")
    if subscription.status in [MembershipStatus.CANCELLED, MembershipStatus.EXPIRED]:
        return subscription
    subscription.status = MembershipStatus.CANCELLED
    subscription.cancelled_at = timezone.now()
    subscription.save(update_fields=["status", "cancelled_at", "updated_at"])
    if subscription.benefit_code_id and subscription.benefit_code.is_active:
        subscription.benefit_code.is_active = False
        subscription.benefit_code.save(update_fields=["is_active", "updated_at"])
    return subscription


def expire_due_memberships(*, now=None, limit=200):
    now = now or timezone.now()
    ids = list(
        MembershipSubscription.objects.filter(
            status=MembershipStatus.ACTIVE,
            ends_at__isnull=False,
            ends_at__lte=now,
        ).order_by("ends_at").values_list("pk", flat=True)[:limit]
    )
    count = 0
    for subscription_id in ids:
        with transaction.atomic():
            subscription = MembershipSubscription.objects.select_for_update().select_related("benefit_code").get(pk=subscription_id)
            if subscription.status != MembershipStatus.ACTIVE or not subscription.ends_at or subscription.ends_at > now:
                continue
            subscription.status = MembershipStatus.EXPIRED
            subscription.expired_at = now
            subscription.save(update_fields=["status", "expired_at", "updated_at"])
            if subscription.benefit_code_id and subscription.benefit_code.is_active:
                subscription.benefit_code.is_active = False
                subscription.benefit_code.save(update_fields=["is_active", "updated_at"])
            count += 1
    return count


@transaction.atomic
def redeem_reward(*, user, reward):
    reward = LoyaltyReward.objects.select_for_update().select_related("program", "program__organization", "promotion", "created_by").get(pk=reward.pk)
    now = timezone.now()
    if not reward.is_active or not reward.program.is_active:
        raise ValidationError("Cette récompense n'est pas disponible.")
    if reward.starts_at and now < reward.starts_at:
        raise ValidationError("Cette récompense n'est pas encore disponible.")
    if reward.ends_at and now > reward.ends_at:
        raise ValidationError("Cette récompense a expiré.")
    account = LoyaltyAccount.objects.select_for_update().filter(program=reward.program, user=user).first()
    if not account:
        raise ValidationError("Vous n'avez pas encore de compte fidélité pour cet organisateur.")
    used = LoyaltyRewardRedemption.objects.filter(reward=reward, user=user, status="redeemed").count()
    if used >= reward.max_redemptions_per_member:
        raise ValidationError("Vous avez déjà utilisé cette récompense le nombre maximum de fois autorisé.")
    if account.points_balance < reward.points_cost:
        raise ValidationError("Solde de points insuffisant.")
    redemption = LoyaltyRewardRedemption.objects.create(
        account=account,
        reward=reward,
        user=user,
        points_cost=reward.points_cost,
    )
    if reward.promotion_id:
        redemption.promotion_code = _create_private_benefit_code(
            promotion=reward.promotion,
            created_by=reward.created_by,
            starts_at=now,
            ends_at=reward.ends_at,
            prefix="RWD",
        )
        redemption.save(update_fields=["promotion_code"])
    _debit_points(
        account=account,
        points=reward.points_cost,
        kind=LedgerKind.REWARD,
        description=f"Récompense {reward.name}",
        idempotency_key=f"reward:{redemption.pk}",
        reward_redemption=redemption,
    )
    transaction.on_commit(
        lambda: _notify(
            user,
            title=f"Récompense obtenue — {reward.name}",
            message=f"{reward.points_cost} points ont été utilisés chez {reward.program.organization.name}.",
            dedup_key=f"reward-redeemed:{redemption.pk}",
            organization_id=reward.program.organization_id,
        )
    )
    return redemption


@transaction.atomic
def adjust_points(*, actor, account, points, reason):
    account = LoyaltyAccount.objects.select_for_update().select_related("program__organization", "user").get(pk=account.pk)
    if not user_can_manage_loyalty_strategy(actor, account.program.organization):
        raise PermissionDenied("Vous ne pouvez pas ajuster ce compte fidélité.")
    points = int(points)
    if points == 0:
        raise ValidationError("L'ajustement ne peut pas être nul.")
    key = f"adjustment:{uuid.uuid4()}"
    if points > 0:
        return _credit_points(
            program=account.program,
            user=account.user,
            points=points,
            kind=LedgerKind.ADJUSTMENT,
            description=reason or "Ajustement manuel",
            idempotency_key=key,
            created_by=actor,
        )
    return _debit_points(
        account=account,
        points=abs(points),
        kind=LedgerKind.ADJUSTMENT,
        description=reason or "Ajustement manuel",
        idempotency_key=key,
        created_by=actor,
    )
