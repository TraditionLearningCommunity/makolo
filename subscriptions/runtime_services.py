from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from organizations.models import Organization

from .contracts import (
    PlanVersionStatus,
    SubscriptionItemStatus,
    SubscriptionPlanType,
    SubscriptionStatus,
    SubscriptionSubjectType,
)
from .runtime_models import EntitlementGrant, Subscription, SubscriptionItem
from .selectors import get_current_default_base_plan


class SubscriptionBootstrapError(ValidationError):
    pass


class SubscriptionStateError(ValidationError):
    pass


def _subject_type(*, profile=None, space=None):
    if bool(profile) == bool(space):
        raise SubscriptionStateError("Indiquez exactement un Profile ou un Space.")
    return SubscriptionSubjectType.PROFILE if profile is not None else SubscriptionSubjectType.SPACE


def _validate_acquirable_version(subscription, plan_version):
    plan = plan_version.plan
    if not plan.is_active:
        raise SubscriptionStateError("Un Plan inactif ne peut pas être acquis.")
    if plan_version.status != PlanVersionStatus.PUBLISHED:
        raise SubscriptionStateError("Seule une PlanVersion publiée peut être acquise.")
    if subscription.subject_type != plan.subject_type:
        raise SubscriptionStateError("Le Plan ne cible pas le sujet de cette Subscription.")


@transaction.atomic
def add_subscription_item(*, subscription, plan_version, status=SubscriptionItemStatus.ACTIVE, starts_at=None):
    subscription = Subscription.objects.select_for_update().get(pk=subscription.pk)
    plan_version = plan_version.__class__.objects.select_for_update().select_related("plan").get(pk=plan_version.pk)
    _validate_acquirable_version(subscription, plan_version)
    plan = plan_version.plan

    if subscription.status == SubscriptionStatus.CLOSED:
        raise SubscriptionStateError("Une Subscription fermée ne peut pas acquérir de nouvel Item.")
    if status not in {SubscriptionItemStatus.ACTIVE, SubscriptionItemStatus.SCHEDULED}:
        raise SubscriptionStateError("Un nouvel Item doit être actif ou planifié.")

    active = SubscriptionItem.objects.select_for_update().filter(
        subscription=subscription,
        status=SubscriptionItemStatus.ACTIVE,
    )
    if status == SubscriptionItemStatus.ACTIVE:
        if plan.plan_type == SubscriptionPlanType.BASE:
            existing = active.filter(item_type=SubscriptionPlanType.BASE).first()
            if existing:
                raise SubscriptionStateError("Cette Subscription possède déjà un BASE actif.")
        else:
            existing = active.filter(item_type=SubscriptionPlanType.ADDON, plan=plan).first()
            if existing:
                raise SubscriptionStateError("Cet add-on est déjà actif pour cette Subscription.")

    item = SubscriptionItem(
        subscription=subscription,
        plan=plan,
        plan_version=plan_version,
        item_type=plan.plan_type,
        status=status,
        starts_at=starts_at or timezone.now(),
    )
    try:
        item.save()
    except IntegrityError as exc:
        raise SubscriptionStateError("Un Item concurrent viole un invariant Subscription.") from exc
    return item


@transaction.atomic
def end_subscription_item(*, item, reason, ended_at=None):
    item = SubscriptionItem.objects.select_for_update().get(pk=item.pk)
    if item.status == SubscriptionItemStatus.ENDED:
        return item
    item.status = SubscriptionItemStatus.ENDED
    item.ends_at = ended_at or timezone.now()
    item.ended_reason = (reason or "").strip()
    if not item.ended_reason:
        raise SubscriptionStateError("La fin d'un SubscriptionItem doit être justifiée.")
    item.save(update_fields=["status", "ends_at", "ended_reason", "updated_at"])
    return item


def _ensure_default_base(subscription):
    default_plan = get_current_default_base_plan(subscription.subject_type)
    if default_plan is None or default_plan.current_version_id is None:
        raise SubscriptionBootstrapError(
            f"Aucun BASE publié par défaut n'est disponible pour {subscription.subject_type}."
        )

    active_base = SubscriptionItem.objects.select_for_update().filter(
        subscription=subscription,
        status=SubscriptionItemStatus.ACTIVE,
        item_type=SubscriptionPlanType.BASE,
    ).first()
    if active_base:
        if active_base.plan.subject_type != subscription.subject_type:
            raise SubscriptionBootstrapError("Le BASE actif existant est incompatible avec le sujet.")
        return active_base

    return add_subscription_item(
        subscription=subscription,
        plan_version=default_plan.current_version,
        status=SubscriptionItemStatus.ACTIVE,
    )


@transaction.atomic
def ensure_subscription_for_profile(profile):
    User = get_user_model()
    profile = User.objects.select_for_update().get(pk=profile.pk)
    default_plan = get_current_default_base_plan(SubscriptionSubjectType.PROFILE)
    if default_plan is None or default_plan.current_version_id is None:
        raise SubscriptionBootstrapError("Aucun BASE Profile publié par défaut n'est disponible.")
    try:
        subscription, _ = Subscription.objects.get_or_create(profile=profile, defaults={"status": SubscriptionStatus.ACTIVE})
    except IntegrityError:
        subscription = Subscription.objects.get(profile=profile)
    subscription = Subscription.objects.select_for_update().get(pk=subscription.pk)
    _ensure_default_base(subscription)
    return subscription


@transaction.atomic
def ensure_subscription_for_space(space):
    space = Organization.objects.select_for_update().get(pk=space.pk)
    default_plan = get_current_default_base_plan(SubscriptionSubjectType.SPACE)
    if default_plan is None or default_plan.current_version_id is None:
        raise SubscriptionBootstrapError("Aucun BASE Space publié par défaut n'est disponible.")
    try:
        subscription, _ = Subscription.objects.get_or_create(space=space, defaults={"status": SubscriptionStatus.ACTIVE})
    except IntegrityError:
        subscription = Subscription.objects.get(space=space)
    subscription = Subscription.objects.select_for_update().get(pk=subscription.pk)
    _ensure_default_base(subscription)
    return subscription


def ensure_subscription_for_subject(subject):
    User = get_user_model()
    if isinstance(subject, User):
        return ensure_subscription_for_profile(subject)
    if isinstance(subject, Organization):
        return ensure_subscription_for_space(subject)
    raise SubscriptionBootstrapError("Le sujet doit être un Profile ou un Space canonique.")


@transaction.atomic
def create_entitlement_grant(
    *,
    feature,
    value,
    reason,
    profile=None,
    space=None,
    granted_by=None,
    valid_from=None,
    valid_until=None,
):
    _subject_type(profile=profile, space=space)
    grant = EntitlementGrant(
        profile=profile,
        space=space,
        feature=feature,
        value=value,
        reason=(reason or "").strip(),
        granted_by=granted_by,
        valid_from=valid_from or timezone.now(),
        valid_until=valid_until,
    )
    if not grant.reason:
        raise SubscriptionStateError("Un Grant doit avoir une raison d'audit concise.")
    grant.save()
    return grant


@transaction.atomic
def revoke_entitlement_grant(*, grant, actor=None, reason):
    grant = EntitlementGrant.objects.select_for_update().get(pk=grant.pk)
    if grant.revoked_at is not None:
        return grant
    reason = (reason or "").strip()
    if not reason:
        raise SubscriptionStateError("La révocation d'un Grant doit être justifiée.")
    grant.revoked_by = actor
    grant.revoked_at = timezone.now()
    grant.revocation_reason = reason
    grant.save(update_fields=["revoked_by", "revoked_at", "revocation_reason", "updated_at"])
    return grant
