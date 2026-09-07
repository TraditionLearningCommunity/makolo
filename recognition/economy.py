from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from subscriptions.models import FeatureDefinition
from subscriptions.runtime_services import create_entitlement_grant

from .models import RecognitionRedemption, RedemptionStatus, RewardDefinition, RewardKind
from .services import refund_spend, spend_points


def _beneficiary_key(*, profile=None, space=None):
    if bool(profile) == bool(space):
        raise ValidationError("Choisissez exactement un bénéficiaire Profile ou Space.")
    return ("profile", profile.pk) if profile is not None else ("space", space.pk)


def _check_eligibility(*, owner_account, reward, beneficiary_profile=None, beneficiary_space=None):
    eligibility = reward.eligibility or {}
    beneficiary_type, beneficiary_id = _beneficiary_key(profile=beneficiary_profile, space=beneficiary_space)
    allowed_subjects = set(eligibility.get("beneficiary_subject_types") or ["profile", "space"])
    if beneficiary_type not in allowed_subjects:
        raise ValidationError("Ce bénéficiaire n'est pas éligible à cette Reward.")
    min_lifetime = int(eligibility.get("owner_lifetime_earned_gte", 0) or 0)
    if owner_account.lifetime_earned < min_lifetime:
        raise ValidationError("Le compte propriétaire n'est pas encore éligible à cette Reward.")
    max_owner = eligibility.get("max_per_owner")
    if max_owner is not None:
        used = reward.redemptions.exclude(status=RedemptionStatus.CANCELLED).filter(owner_account=owner_account).count()
        if used >= int(max_owner):
            raise ValidationError("La limite d'utilisation de cette Reward pour ce compte est atteinte.")
    max_beneficiary = eligibility.get("max_per_beneficiary")
    if max_beneficiary is not None:
        query = {f"beneficiary_{beneficiary_type}_id": beneficiary_id}
        used = reward.redemptions.exclude(status=RedemptionStatus.CANCELLED).filter(**query).count()
        if used >= int(max_beneficiary):
            raise ValidationError("La limite de cette Reward pour ce bénéficiaire est atteinte.")


def _mark_fulfilled(redemption, snapshot):
    redemption.fulfillment_snapshot = snapshot
    redemption.status = RedemptionStatus.FULFILLED
    redemption.fulfilled_at = timezone.now()
    redemption.save(update_fields=["fulfillment_snapshot", "status", "fulfilled_at"])
    return redemption


def _mark_delegated(redemption, *, domain, state, details=None):
    """Persist an actionable owner-domain handoff without pretending that the external effect already happened."""
    snapshot = dict(redemption.fulfillment_snapshot or {})
    snapshot.update({"delegated_domain": domain, "delegation_state": state})
    snapshot.update(details or {})
    redemption.fulfillment_snapshot = snapshot
    redemption.save(update_fields=["fulfillment_snapshot"])
    return redemption


def _fulfill_entitlement(redemption, *, actor_profile=None):
    config = dict(redemption.fulfillment_snapshot or {})
    feature_code = str(config.get("feature_code") or "").strip()
    if not feature_code:
        raise ValidationError("La Reward Entitlement doit déclarer feature_code.")
    feature = FeatureDefinition.objects.filter(code=feature_code, is_active=True).first()
    if feature is None:
        raise ValidationError("La Feature configurée pour cette Reward n'existe pas ou est inactive.")
    duration_days = config.get("duration_days")
    valid_until = None
    if duration_days is not None:
        duration_days = int(duration_days)
        if duration_days < 1:
            raise ValidationError("duration_days doit être positif.")
        valid_until = timezone.now() + timedelta(days=duration_days)
    kwargs = {
        "feature": feature,
        "value": config.get("value", True),
        "reason": f"Recognition reward {redemption.reward.code}:v{redemption.reward.version}",
        "granted_by": actor_profile,
        "valid_until": valid_until,
    }
    if redemption.beneficiary_profile_id: kwargs["profile"] = redemption.beneficiary_profile
    else: kwargs["space"] = redemption.beneficiary_space
    grant = create_entitlement_grant(**kwargs)
    config.update({"fulfilled_domain": "subscriptions", "entitlement_grant_id": str(grant.pk)})
    return _mark_fulfilled(redemption, config)


def _fulfill_access(redemption, *, actor_profile=None):
    from access.models import Access, AccessStatus
    from access.services import issue_access
    from activities.models import Activity, ActivityStatus, Occurrence, OccurrenceStatus
    from capacity.models import CapacityPool

    if not redemption.beneficiary_profile_id:
        raise ValidationError("Un Access canonique appartient à une personne ; cette Reward Access exige un Profile bénéficiaire.")
    config = dict(redemption.fulfillment_snapshot or {})
    activity_id = config.get("activity_id")
    if not activity_id:
        raise ValidationError("La Reward Access doit déclarer activity_id.")
    activity = Activity.objects.filter(pk=activity_id).first()
    if activity is None:
        raise ValidationError("L'Activity configurée pour cette Reward Access n'existe pas.")
    if activity.status in {ActivityStatus.CANCELLED, ActivityStatus.COMPLETED, ActivityStatus.ARCHIVED}:
        raise ValidationError("Cette Activity ne peut plus recevoir de nouvel Access.")
    occurrence = None
    if config.get("occurrence_id"):
        occurrence = Occurrence.objects.filter(pk=config["occurrence_id"], activity=activity).first()
        if occurrence is None:
            raise ValidationError("L'Occurrence configurée n'appartient pas à cette Activity.")
        if occurrence.status in {OccurrenceStatus.CANCELLED, OccurrenceStatus.COMPLETED}:
            raise ValidationError("Cette Occurrence ne peut plus recevoir de nouvel Access.")

    finite = CapacityPool.objects.filter(activity=activity, is_active=True, total_quantity__isnull=False, offers__isnull=True).distinct()
    if occurrence is None:
        if finite.filter(occurrence__isnull=False).exists():
            raise ValidationError("Cette Reward doit préciser une Occurrence car la capacité d'admission est session-scoped.")
        finite = finite.filter(occurrence__isnull=True)
    else:
        finite = finite.filter(Q(occurrence__isnull=True) | Q(occurrence=occurrence))
    if finite.exists():
        raise ValidationError("Cette Reward Access ne peut pas contourner une Capacity finie ; configurez un bénéfice Commerce/Access qui consomme la capacité canonique.")

    active = Access.objects.filter(
        beneficiary=redemption.beneficiary_profile,
        activity=activity,
        status__in=[AccessStatus.PENDING, AccessStatus.VALID],
    )
    active = active.filter(occurrence__isnull=True) if occurrence is None else active.filter(Q(occurrence__isnull=True) | Q(occurrence=occurrence))
    active = active.filter(Q(status=AccessStatus.PENDING) | Q(valid_until__isnull=True) | Q(valid_until__gt=timezone.now()))
    if active.exists():
        raise ValidationError("Le bénéficiaire possède déjà un Access actif pour cette possibilité.")

    duration_days = config.get("duration_days")
    valid_until = None
    if duration_days is not None:
        duration_days = int(duration_days)
        if duration_days < 1: raise ValidationError("duration_days doit être positif.")
        valid_until = timezone.now() + timedelta(days=duration_days)
    kwargs = {
        "beneficiary": redemption.beneficiary_profile,
        "activity": activity,
        "occurrence": occurrence,
        "issued_by": actor_profile,
        "source_key": f"recognition:{redemption.pk}",
        "create_credential": bool(config.get("create_credential", True)),
        "single_use": bool(config.get("single_use", True)),
        "audit_reason": f"Recognition reward {redemption.reward.code}:v{redemption.reward.version}",
    }
    if duration_days is not None:
        kwargs["valid_from"] = timezone.now(); kwargs["valid_until"] = valid_until
    access = issue_access(**kwargs)
    config.update({"fulfilled_domain": "access", "access_id": str(access.pk)})
    return _mark_fulfilled(redemption, config)


def _fulfill_promotion(redemption, *, actor_profile=None):
    from promotions.models import Promotion, PromotionCode

    if not redemption.beneficiary_profile_id:
        raise ValidationError("Une Reward Promotion v1 exige un Profile bénéficiaire.")
    if actor_profile is None or not getattr(actor_profile, "is_authenticated", False):
        raise ValidationError("La création du code Promotion doit être attribuable à un Profile authentifié.")
    config = dict(redemption.fulfillment_snapshot or {})
    promotion_id = config.get("promotion_id")
    promotion = Promotion.objects.filter(pk=promotion_id, is_active=True).first() if promotion_id else None
    if promotion is None:
        raise ValidationError("La Reward Promotion doit référencer une Promotion active existante.")
    code_value = f"R{redemption.pk.hex[:24]}".upper()
    code, created = PromotionCode.objects.get_or_create(
        code=code_value,
        defaults={
            "promotion": promotion, "label": f"Recognition — {redemption.reward.name}"[:120],
            "is_private": True, "is_active": True, "max_redemptions": 1,
            "starts_at": max(filter(None, [promotion.starts_at, timezone.now()]), default=timezone.now()),
            "ends_at": promotion.ends_at, "created_by": actor_profile,
        },
    )
    if not created and code.promotion_id != promotion.pk:
        raise ValidationError("Le code Recognition est déjà lié à une autre Promotion.")
    config.update({"fulfilled_domain": "promotions", "promotion_code_id": str(code.pk), "promotion_code": code.code})
    return _mark_fulfilled(redemption, config)


def _fulfill_introduction(redemption, *, actor_profile=None):
    from social.bilateral_services import create_action_need
    from social.models import ActionNeedIntakePolicy, ActionNeedVisibility

    config = dict(redemption.fulfillment_snapshot or {})
    title = str(config.get("title") or "Mise en relation Makolo").strip()[:180]
    match_kind = str(config.get("match_kind") or "").strip()
    if not match_kind:
        raise ValidationError("La Reward Introduction doit déclarer match_kind.")
    kwargs = {
        "actor": actor_profile,
        "title": title,
        "description": str(config.get("description") or "").strip(),
        "match_kind": match_kind,
        "visibility": ActionNeedVisibility.PRIVATE,
        "intake_policy": ActionNeedIntakePolicy.INVITE_ONLY,
        "candidate_kind": str(config.get("candidate_kind") or "profile"),
    }
    if redemption.beneficiary_profile_id:
        if actor_profile is None or actor_profile.pk != redemption.beneficiary_profile_id:
            raise PermissionDenied("Le Profile bénéficiaire doit accepter et ouvrir lui-même cette mise en relation.")
        kwargs["owner_profile"] = redemption.beneficiary_profile
    else:
        kwargs["space"] = redemption.beneficiary_space
    need = create_action_need(**kwargs)
    config.update({"fulfilled_domain": "action_network", "action_need_id": str(need.pk)})
    return _mark_fulfilled(redemption, config)


def _delegate_payout(redemption):
    config = dict(redemption.fulfillment_snapshot or {})
    amount = config.get("amount")
    currency = str(config.get("currency") or "").strip().upper()
    try: amount = Decimal(str(amount))
    except Exception as exc: raise ValidationError("La Reward Payout doit déclarer un amount explicite.") from exc
    if amount <= 0 or len(currency) != 3:
        raise ValidationError("La Reward Payout exige un amount positif et une currency ISO explicite.")
    # Finance has no canonical primitive that can mint a funded payable from Recognition.
    # Persist the handoff; a real Payment/Payout must later reference actual funds/destination/authority.
    return _mark_delegated(redemption, domain="payments", state="awaiting_finance", details={"requested_amount": str(amount), "currency": currency})


def _delegate_other(redemption):
    config = dict(redemption.fulfillment_snapshot or {})
    owner_domain = str(config.get("owner_domain") or "").strip()
    if not owner_domain:
        raise ValidationError("Une Reward de type OTHER doit déclarer owner_domain.")
    return _mark_delegated(redemption, domain=owner_domain[:80], state="awaiting_owner_domain")


def fulfill_redemption(redemption, *, actor_profile=None):
    """Delegate every Reward kind to the canonical owning domain or persist an explicit handoff."""
    if redemption.status == RedemptionStatus.FULFILLED: return redemption
    if redemption.status == RedemptionStatus.CANCELLED: raise ValidationError("Une utilisation annulée ne peut pas être réalisée.")
    if (redemption.fulfillment_snapshot or {}).get("consent_state") == "pending":
        raise ValidationError("Le bénéficiaire doit accepter cette Reward avant réalisation.")
    handlers = {
        RewardKind.ENTITLEMENT: _fulfill_entitlement,
        RewardKind.ACCESS: _fulfill_access,
        RewardKind.PROMOTION: _fulfill_promotion,
        RewardKind.INTRODUCTION: _fulfill_introduction,
    }
    if redemption.reward.kind in handlers:
        return handlers[redemption.reward.kind](redemption, actor_profile=actor_profile)
    if redemption.reward.kind == RewardKind.PAYOUT: return _delegate_payout(redemption)
    return _delegate_other(redemption)


@transaction.atomic
def redeem_reward(*, owner_account, reward, idempotency_key, actor_profile=None, beneficiary_profile=None, beneficiary_space=None):
    _beneficiary_key(profile=beneficiary_profile, space=beneficiary_space)
    key = (idempotency_key or "").strip()
    if not key: raise ValidationError("Une utilisation de crédits exige une clé d'idempotence.")
    existing = RecognitionRedemption.objects.filter(idempotency_key=key).select_related("reward").first()
    if existing: return existing

    reward = RewardDefinition.objects.select_for_update().get(pk=reward.pk); now = timezone.now()
    if not reward.is_active or (reward.valid_from and now < reward.valid_from) or (reward.valid_until and now >= reward.valid_until):
        raise ValidationError("Cette Reward n'est pas disponible maintenant.")
    if reward.stock is not None and reward.redemptions.exclude(status=RedemptionStatus.CANCELLED).count() >= reward.stock:
        raise ValidationError("Cette Reward n'est plus disponible.")
    owner_is_beneficiary = (
        (owner_account.profile_id and beneficiary_profile and owner_account.profile_id == beneficiary_profile.pk)
        or (owner_account.space_id and beneficiary_space and owner_account.space_id == beneficiary_space.pk)
    )
    if not owner_is_beneficiary and not reward.beneficiary_allowed:
        raise ValidationError("Cette Reward ne peut pas être utilisée pour un autre bénéficiaire.")
    _check_eligibility(owner_account=owner_account, reward=reward, beneficiary_profile=beneficiary_profile, beneficiary_space=beneficiary_space)

    spend_points(
        account=owner_account, points=reward.points_cost, idempotency_key=f"reward-spend:{key}",
        description=f"Reward : {reward.name}", actor_profile=actor_profile,
        metadata={"reward_id": str(reward.pk), "beneficiary_profile_id": str(getattr(beneficiary_profile, "pk", "")), "beneficiary_space_id": str(getattr(beneficiary_space, "pk", ""))},
    )
    snapshot = dict(reward.fulfillment or {})
    snapshot.update({"reward_code": reward.code, "reward_version": reward.version, "consent_state": "pending" if (reward.acceptance_required and not owner_is_beneficiary) else "not_required"})
    redemption = RecognitionRedemption.objects.create(
        owner_account=owner_account, reward=reward, beneficiary_profile=beneficiary_profile, beneficiary_space=beneficiary_space,
        points_cost=reward.points_cost, status=RedemptionStatus.REQUESTED, idempotency_key=key, fulfillment_snapshot=snapshot,
    )
    return fulfill_redemption(redemption, actor_profile=actor_profile) if snapshot["consent_state"] != "pending" else redemption


def _validate_decision_subject(redemption, *, beneficiary_profile=None, beneficiary_space=None):
    if redemption.beneficiary_profile_id:
        if beneficiary_profile is None or beneficiary_profile.pk != redemption.beneficiary_profile_id or beneficiary_space is not None:
            raise ValidationError("Seul le Profile bénéficiaire peut décider pour cette Reward.")
        return beneficiary_profile
    if redemption.beneficiary_space_id:
        if beneficiary_space is None or beneficiary_space.pk != redemption.beneficiary_space_id or beneficiary_profile is not None:
            raise ValidationError("Seul l'Espace bénéficiaire, via une autorité explicite, peut décider pour cette Reward.")
        return beneficiary_space
    raise ValidationError("Cette Reward n'a pas de bénéficiaire valide.")


@transaction.atomic
def accept_redemption(*, redemption, beneficiary_profile=None, beneficiary_space=None, actor_profile=None):
    redemption = RecognitionRedemption.objects.select_for_update(of=("self",)).select_related("reward", "beneficiary_profile", "beneficiary_space").get(pk=redemption.pk)
    snapshot = dict(redemption.fulfillment_snapshot or {})
    if snapshot.get("consent_state") != "pending": return redemption
    _validate_decision_subject(redemption, beneficiary_profile=beneficiary_profile, beneficiary_space=beneficiary_space)
    snapshot.update({"consent_state": "accepted", "consent_at": timezone.now().isoformat(), "consent_actor_profile_id": str(getattr(actor_profile, "pk", ""))})
    redemption.fulfillment_snapshot = snapshot; redemption.save(update_fields=["fulfillment_snapshot"])
    return fulfill_redemption(redemption, actor_profile=actor_profile or beneficiary_profile)


@transaction.atomic
def decline_redemption(*, redemption, beneficiary_profile=None, beneficiary_space=None, actor_profile=None):
    redemption = RecognitionRedemption.objects.select_for_update(of=("self",)).select_related("reward", "owner_account", "beneficiary_profile", "beneficiary_space").get(pk=redemption.pk)
    snapshot = dict(redemption.fulfillment_snapshot or {})
    if snapshot.get("consent_state") != "pending": raise ValidationError("Cette Reward n'attend pas de décision du bénéficiaire.")
    _validate_decision_subject(redemption, beneficiary_profile=beneficiary_profile, beneficiary_space=beneficiary_space)
    refund_spend(
        account=redemption.owner_account, points=redemption.points_cost, idempotency_key=f"reward-refund:{redemption.idempotency_key}",
        description=f"Restitution Reward refusée : {redemption.reward.name}", actor_profile=actor_profile or beneficiary_profile,
        metadata={"redemption_id": str(redemption.pk)},
    )
    snapshot.update({"consent_state": "declined", "consent_at": timezone.now().isoformat(), "consent_actor_profile_id": str(getattr(actor_profile, "pk", ""))})
    redemption.fulfillment_snapshot = snapshot; redemption.status = RedemptionStatus.CANCELLED
    redemption.save(update_fields=["fulfillment_snapshot", "status"]); return redemption
