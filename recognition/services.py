from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal, ROUND_FLOOR
from typing import Iterable

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Sum
from django.utils import timezone

from .contracts import ImpactChannel, RecognitionLedgerKind, RecognitionWindowStatus, TemporalProfile
from .models import (
    RecognitionAccount, RecognitionAccrual, RecognitionCursor, RecognitionEvaluationWindow,
    RecognitionLedgerEntry, RecognitionSliceReceipt,
)


@dataclass(frozen=True, slots=True)
class AttributionShare:
    share: Decimal
    profile: object | None = None
    space: object | None = None
    description: str = "Impact Makolo reconnu"

    def subject_key(self) -> str:
        if bool(self.profile) == bool(self.space):
            raise ValidationError("Une attribution vise exactement un Profile ou un Space.")
        return f"profile:{self.profile.pk}" if self.profile is not None else f"space:{self.space.pk}"


@dataclass(frozen=True, slots=True)
class SliceProcessResult:
    receipt: RecognitionSliceReceipt
    created: bool
    grants: tuple[RecognitionLedgerEntry, ...]


def _validate_policy_version(value: str) -> str:
    value = (value or "").strip()
    if not value:
        raise ValidationError("policy_version est obligatoire.")
    return value


def get_or_create_account(*, profile=None, space=None) -> RecognitionAccount:
    if bool(profile) == bool(space):
        raise ValidationError("Un compte Recognition appartient exactement à un Profile ou un Space.")
    lookup = {"profile": profile} if profile is not None else {"space": space}
    try:
        account, _ = RecognitionAccount.objects.get_or_create(**lookup)
    except IntegrityError:
        account = RecognitionAccount.objects.get(**lookup)
    return account


def ensure_cursor(*, key="network-utility", policy_version: str, window_size_hours=24, start_at=None):
    policy_version = _validate_policy_version(policy_version)
    if not 1 <= window_size_hours <= 168:
        raise ValidationError("La fenêtre Recognition doit être comprise entre 1 et 168 heures.")
    cursor, created = RecognitionCursor.objects.get_or_create(
        key=key,
        defaults={
            "policy_version": policy_version,
            "window_size_hours": window_size_hours,
            "last_completed_end": start_at or timezone.now(),
        },
    )
    if not created:
        if cursor.window_size_hours != window_size_hours:
            raise ValidationError("La cadence d'un curseur existant ne change pas silencieusement.")
        if cursor.policy_version != policy_version:
            raise ValidationError("La Policy d'un curseur existant doit changer explicitement à une frontière de fenêtre.")
    return cursor


def get_due_window(*, cursor, now=None):
    now = now or timezone.now()
    starts_at = cursor.last_completed_end
    ends_at = starts_at + timedelta(hours=cursor.window_size_hours)
    if ends_at > now:
        return None
    window, created = RecognitionEvaluationWindow.objects.get_or_create(
        cursor=cursor, starts_at=starts_at, ends_at=ends_at,
        defaults={"policy_version": cursor.policy_version},
    )
    if not created and window.policy_version != cursor.policy_version:
        raise ValidationError("Une fenêtre existante conserve la Policy avec laquelle elle a été ouverte.")
    return window


def mark_window_running(window):
    with transaction.atomic():
        window = RecognitionEvaluationWindow.objects.select_for_update().get(pk=window.pk)
        if window.status != RecognitionWindowStatus.COMPLETED.value:
            window.status = RecognitionWindowStatus.RUNNING.value
            window.save(update_fields=["status", "updated_at"])
    return window


def complete_window(*, window, cursor):
    with transaction.atomic():
        window = RecognitionEvaluationWindow.objects.select_for_update().get(pk=window.pk)
        cursor = RecognitionCursor.objects.select_for_update().get(pk=cursor.pk)
        if window.cursor_id != cursor.pk:
            raise ValidationError("La fenêtre Recognition appartient à un autre curseur.")
        if window.starts_at != cursor.last_completed_end:
            if window.status == RecognitionWindowStatus.COMPLETED.value and cursor.last_completed_end >= window.ends_at:
                return window
            raise ValidationError("La fenêtre Recognition ne correspond pas au watermark courant.")
        if window.pool_points != window.issued_points + window.unattributed_points:
            raise ValidationError("La conservation du pool Recognition est invalide.")
        window.status = RecognitionWindowStatus.COMPLETED.value
        window.completed_at = timezone.now()
        window.save(update_fields=["status", "completed_at", "updated_at"])
        cursor.last_completed_end = window.ends_at
        cursor.save(update_fields=["last_completed_end", "updated_at"])
    return window


def _grant_idempotency_key(*, slice_key, subject_key):
    return "recognition-grant:" + hashlib.sha256(f"{slice_key}|{subject_key}".encode()).hexdigest()


def _pending_idempotency_key(*, slice_key, subject_key):
    return "recognition-pending:" + hashlib.sha256(f"{slice_key}|{subject_key}".encode()).hexdigest()


def _normalize_shares(shares: Iterable[AttributionShare]):
    rows = tuple(shares); total = Decimal("0"); seen = set()
    for item in rows:
        key = item.subject_key()
        if key in seen:
            raise ValidationError("Un sujet ne doit apparaître qu'une fois dans les parts d'une slice.")
        seen.add(key); share = Decimal(item.share)
        if not share.is_finite() or share < 0 or share > 1:
            raise ValidationError("Une part d'attribution doit être comprise entre 0 et 1.")
        total += share
    if total > 1:
        raise ValidationError("La somme des parts attribuées ne peut pas dépasser 1.")
    return rows


def _integer_allocations(pool_points, shares):
    if pool_points < 0:
        raise ValidationError("Le pool de Points ne peut pas être négatif.")
    total_share = sum((Decimal(item.share) for item in shares), Decimal("0")); rows = []; floor_total = 0
    for item in shares:
        exact = Decimal(pool_points) * Decimal(item.share); floor_value = int(exact.to_integral_value(rounding=ROUND_FLOOR))
        floor_total += floor_value; rows.append({"item": item, "points": floor_value, "remainder": exact-floor_value, "key": item.subject_key()})
    exact = Decimal(pool_points) * (Decimal("1") - total_share); unattributed = int(exact.to_integral_value(rounding=ROUND_FLOOR))
    floor_total += unattributed; rows.append({"item": None, "points": unattributed, "remainder": exact-unattributed, "key": "unattributed"})
    for row in sorted(rows, key=lambda row: (-row["remainder"], row["key"]))[:pool_points-floor_total]: row["points"] += 1
    return ([(row["item"], row["points"]) for row in rows if row["item"] is not None and row["points"] > 0], next(row["points"] for row in rows if row["item"] is None))


def _apply_earned_projection(account, points):
    """Earned credits are final Recognition; an internal deficit only delays availability."""
    account.lifetime_earned += points
    absorbed = min(account.correction_deficit, points)
    account.correction_deficit -= absorbed
    account.points_balance += points - absorbed
    return absorbed


@transaction.atomic
def process_impact_slice(*, window, slice_key, accrual_key, channel, temporal_profile, occurred_at, available_at, impact_delta, attribution_shares, points_target_for_cumulative, policy_version, metadata=None, maturation_hours=0):
    policy_version = _validate_policy_version(policy_version); slice_key=(slice_key or "").strip(); accrual_key=(accrual_key or "").strip(); impact_delta=Decimal(impact_delta)
    channel=getattr(channel,"value",channel); temporal_profile=getattr(temporal_profile,"value",temporal_profile)
    maturation_hours=max(0, min(int(maturation_hours or 0), 8760))
    if not slice_key or not accrual_key: raise ValidationError("slice_key et accrual_key sont obligatoires.")
    if not impact_delta.is_finite() or impact_delta < 0: raise ValidationError("Une slice v1 porte un delta d'impact fini, positif ou nul ; les corrections sont explicites.")
    if channel not in {item.value for item in ImpactChannel}: raise ValidationError("Canal d'impact Recognition inconnu.")
    if temporal_profile not in {item.value for item in TemporalProfile}: raise ValidationError("Profil temporel Recognition inconnu.")
    existing=RecognitionSliceReceipt.objects.filter(slice_key=slice_key).first()
    if existing: return SliceProcessResult(existing,False,tuple(existing.ledger_entries.all()))
    window=RecognitionEvaluationWindow.objects.select_for_update().get(pk=window.pk)
    existing=RecognitionSliceReceipt.objects.filter(slice_key=slice_key).first()
    if existing: return SliceProcessResult(existing,False,tuple(existing.ledger_entries.all()))
    if window.status==RecognitionWindowStatus.COMPLETED.value: raise ValidationError("Une fenêtre terminée n'accepte plus de nouvelles slices.")
    if window.policy_version!=policy_version: raise ValidationError("La slice doit utiliser la même Policy que sa fenêtre.")
    if available_at is None or not (window.starts_at <= available_at < window.ends_at): raise ValidationError("available_at doit appartenir à la fenêtre d'évaluation [starts_at, ends_at).")
    shares=_normalize_shares(attribution_shares)
    accrual,_=RecognitionAccrual.objects.get_or_create(accrual_key=accrual_key,policy_version=policy_version,defaults={"channel":channel})
    accrual=RecognitionAccrual.objects.select_for_update().get(pk=accrual.pk)
    if accrual.channel!=channel: raise ValidationError("Un accrual_key ne peut pas changer de canal.")
    previous_target=accrual.matured_points; cumulative=accrual.cumulative_impact+impact_delta; new_target=int(points_target_for_cumulative(cumulative))
    if new_target<previous_target: raise ValidationError("Une Policy de grant ne peut pas réduire silencieusement un target déjà maturé.")
    pool_points=new_target-previous_target; allocations,unattributed=_integer_allocations(pool_points,shares); issued=sum(points for _,points in allocations)
    if pool_points != issued+unattributed: raise ValidationError("La conservation du pool de Points a échoué.")
    accrual.cumulative_impact=cumulative; accrual.matured_points=new_target; accrual.save(update_fields=["cumulative_impact","matured_points","updated_at"])
    receipt=RecognitionSliceReceipt.objects.create(window=window,accrual=accrual,slice_key=slice_key,policy_version=policy_version,channel=channel,temporal_profile=temporal_profile,occurred_at=occurred_at,available_at=available_at,impact_delta=impact_delta,pool_points=pool_points,issued_points=issued,unattributed_points=unattributed,metadata=metadata or {})
    grants=[]
    for share,points in allocations:
        account=get_or_create_account(profile=share.profile,space=share.space); account=RecognitionAccount.objects.select_for_update().get(pk=account.pk)
        if maturation_hours:
            matures_at=available_at + timedelta(hours=maturation_hours)
            entry=RecognitionLedgerEntry.objects.create(account=account,kind=RecognitionLedgerKind.PENDING.value,points=points,description=(share.description or "Impact Makolo en maturation")[:255],idempotency_key=_pending_idempotency_key(slice_key=slice_key,subject_key=share.subject_key()),recognized_slice=receipt,policy_version=policy_version,metadata={"slice_key":slice_key,"accrual_key":accrual_key,"matures_at":matures_at.isoformat()})
            account.pending_points+=points
            account.save(update_fields=["pending_points","updated_at"])
        else:
            absorbed=_apply_earned_projection(account,points)
            entry=RecognitionLedgerEntry.objects.create(account=account,kind=RecognitionLedgerKind.GRANT.value,points=points,description=(share.description or "Impact Makolo reconnu")[:255],idempotency_key=_grant_idempotency_key(slice_key=slice_key,subject_key=share.subject_key()),recognized_slice=receipt,policy_version=policy_version,metadata={"slice_key":slice_key,"accrual_key":accrual_key,"absorbed_correction_deficit":absorbed})
            account.save(update_fields=["points_balance","correction_deficit","lifetime_earned","updated_at"])
        grants.append(entry)
    window.processed_slices+=1; window.pool_points+=pool_points; window.issued_points+=issued; window.unattributed_points+=unattributed
    window.save(update_fields=["processed_slices","pool_points","issued_points","unattributed_points","updated_at"])
    return SliceProcessResult(receipt,True,tuple(grants))


@transaction.atomic
def release_due_pending_grants(*, now=None, limit=500):
    """Move matured pending Recognition into the available balance exactly once."""
    now = now or timezone.now()
    released = 0
    candidates = list(
        RecognitionLedgerEntry.objects.filter(kind=RecognitionLedgerKind.PENDING.value)
        .select_related("account", "recognized_slice")
        .order_by("created_at", "id")[: max(1, int(limit))]
    )
    for pending in candidates:
        matures_at = (pending.metadata or {}).get("matures_at")
        if not matures_at:
            continue
        try:
            due_at = timezone.datetime.fromisoformat(matures_at)
        except (TypeError, ValueError):
            continue
        if timezone.is_naive(due_at):
            due_at = timezone.make_aware(due_at, timezone.get_current_timezone())
        if due_at > now:
            continue
        release_key = f"recognition-release:{pending.pk}"
        if RecognitionLedgerEntry.objects.filter(idempotency_key=release_key).exists():
            continue
        account = RecognitionAccount.objects.select_for_update().get(pk=pending.account_id)
        if account.pending_points < pending.points:
            raise ValidationError("La projection pending Recognition est incohérente avec le ledger.")
        absorbed = _apply_earned_projection(account, pending.points)
        account.pending_points -= pending.points
        grant = RecognitionLedgerEntry.objects.create(
            account=account,
            kind=RecognitionLedgerKind.GRANT.value,
            points=pending.points,
            description=pending.description.replace("en maturation", "reconnu")[:255],
            idempotency_key=release_key,
            recognized_slice=pending.recognized_slice,
            policy_version=pending.policy_version,
            metadata={"pending_entry_id": str(pending.pk), "absorbed_correction_deficit": absorbed},
        )
        account.save(update_fields=["points_balance","pending_points","correction_deficit","lifetime_earned","updated_at"])
        evaluation = getattr(pending.recognized_slice, "object_evaluation", None) if pending.recognized_slice_id else None
        if evaluation is not None:
            from .achievements import grant_due_achievements
            grant_due_achievements(account=account, evaluation=evaluation)
        released += grant.points
    return released


@transaction.atomic
def spend_points(*, account, points, idempotency_key, description, actor_profile=None, metadata=None):
    points=int(points); key=(idempotency_key or "").strip()
    if points<=0: raise ValidationError("Le nombre de Points à utiliser doit être positif.")
    if not key: raise ValidationError("Une dépense de Points exige une clé d'idempotence.")
    existing=RecognitionLedgerEntry.objects.filter(idempotency_key=key).first()
    if existing:
        if existing.account_id!=account.pk or existing.kind!=RecognitionLedgerKind.SPEND.value or existing.points!=-points: raise ValidationError("Cette clé d'idempotence appartient à une autre opération ou un autre montant.")
        return existing
    account=RecognitionAccount.objects.select_for_update().get(pk=account.pk); existing=RecognitionLedgerEntry.objects.filter(idempotency_key=key).first()
    if existing: return existing
    if account.points_balance<points: raise ValidationError("Solde de Points insuffisant.")
    entry=RecognitionLedgerEntry.objects.create(account=account,kind=RecognitionLedgerKind.SPEND.value,points=-points,description=(description or "Utilisation de Points")[:255],idempotency_key=key,actor_profile=actor_profile,metadata=metadata or {})
    account.points_balance-=points; account.lifetime_spent+=points; account.save(update_fields=["points_balance","lifetime_spent","updated_at"]); return entry


@transaction.atomic
def refund_spend(*, account, points, idempotency_key, description, actor_profile=None, metadata=None):
    points=int(points); key=(idempotency_key or "").strip()
    existing=RecognitionLedgerEntry.objects.filter(idempotency_key=key).first()
    if existing: return existing
    if points<=0 or not key: raise ValidationError("Une restitution de crédits doit être positive et idempotente.")
    account=RecognitionAccount.objects.select_for_update().get(pk=account.pk)
    entry=RecognitionLedgerEntry.objects.create(account=account,kind=RecognitionLedgerKind.ADJUSTMENT.value,points=points,description=description[:255],idempotency_key=key,actor_profile=actor_profile,metadata=metadata or {})
    account.points_balance+=points; account.lifetime_spent=max(0,account.lifetime_spent-points); account.save(update_fields=["points_balance","lifetime_spent","updated_at"]); return entry


@transaction.atomic
def apply_correction(*, account, points_to_remove, idempotency_key, reason, actor_profile=None):
    """Correct an internal Recognition error without ever exposing a negative user balance."""
    points=int(points_to_remove); key=(idempotency_key or "").strip(); reason=(reason or "").strip()
    if points<=0 or not key or not reason: raise ValidationError("Une correction exige un montant positif, une clé et une justification.")
    existing=RecognitionLedgerEntry.objects.filter(idempotency_key=key).first()
    if existing: return existing
    account=RecognitionAccount.objects.select_for_update().get(pk=account.pk)
    immediately_removed=min(account.points_balance,points); deficit=points-immediately_removed
    entry=RecognitionLedgerEntry.objects.create(account=account,kind=RecognitionLedgerKind.ADJUSTMENT.value,points=-points,description=f"Correction Recognition : {reason}"[:255],idempotency_key=key,actor_profile=actor_profile,metadata={"immediately_removed":immediately_removed,"future_offset":deficit})
    account.points_balance-=immediately_removed; account.correction_deficit+=deficit; account.save(update_fields=["points_balance","correction_deficit","updated_at"]); return entry


def reconstructed_balance(account):
    value=account.ledger_entries.exclude(kind=RecognitionLedgerKind.PENDING.value).aggregate(total=Sum("points"))["total"]
    return int(value or 0)
