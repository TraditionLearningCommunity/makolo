from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from django.urls import reverse

from rest_framework import status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from recognition.economy import accept_redemption, decline_redemption, redeem_reward
from recognition.models import RecognitionRedemption
from recognition.selectors import (
    account_for_profile,
    active_rewards,
    redemptions_requiring_beneficiary_response,
)
from recognition.services import get_or_create_account


def _raise_service(exc):
    if hasattr(exc, "message_dict"):
        raise ValidationError(exc.message_dict) from exc
    raise ValidationError(getattr(exc, "messages", [str(exc)])) from exc


def _reward_payload(reward):
    self_eligible = bool(getattr(reward, "recognition_self_eligible", False))
    capabilities = ["redeem"] if self_eligible else []
    links = {}
    if self_eligible:
        links["redeem"] = reverse(
            "recognition_api:reward-redeem",
            kwargs={"reward_id": reward.pk},
        )
    return {
        "id": str(reward.pk),
        "code": reward.code,
        "version": reward.version,
        "name": reward.name,
        "description": reward.description or None,
        "kind": reward.kind,
        "kind_label": reward.get_kind_display(),
        "points_cost": reward.points_cost,
        "beneficiary_allowed": bool(reward.beneficiary_allowed),
        "acceptance_required": bool(reward.acceptance_required),
        "self_eligible": self_eligible,
        "requires_other_beneficiary": bool(
            getattr(reward, "recognition_requires_other_beneficiary", False)
        ),
        "capabilities": capabilities,
        "links": links,
    }


def _redemption_payload(redemption, *, incoming=False):
    consent_state = (redemption.fulfillment_snapshot or {}).get("consent_state")
    capabilities = []
    links = {}
    if incoming and redemption.status == "requested" and consent_state == "pending":
        capabilities = ["accept", "decline"]
        links["accept"] = reverse(
            "recognition_api:redemption-decision",
            kwargs={"redemption_id": redemption.pk, "decision": "accept"},
        )
        links["decline"] = reverse(
            "recognition_api:redemption-decision",
            kwargs={"redemption_id": redemption.pk, "decision": "decline"},
        )
    return {
        "id": str(redemption.pk),
        "reward": {
            "id": str(redemption.reward_id),
            "name": redemption.reward.name,
            "kind": redemption.reward.kind,
        },
        "points_cost": redemption.points_cost,
        "status": redemption.status,
        "status_label": redemption.get_status_display(),
        "consent_state": consent_state,
        "created_at": redemption.created_at,
        "fulfilled_at": redemption.fulfilled_at,
        "capabilities": capabilities,
        "links": links,
    }


def _account_payload(account):
    if account is None:
        return None
    return {
        "id": str(account.pk),
        "points_balance": account.points_balance,
        "pending_points": account.pending_points,
        "lifetime_earned": account.lifetime_earned,
        "lifetime_spent": account.lifetime_spent,
        "unit": "recognition_credit",
        "currency": None,
    }


def _ledger_payload(entry):
    return {
        "id": str(entry.pk),
        "kind": entry.kind,
        "credits_delta": entry.points,
        "description": entry.description,
        "created_at": entry.created_at,
    }


class MyRecognitionAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        account = account_for_profile(request.user)
        rewards = active_rewards(owner_account=account) if account is not None else []
        incoming = list(redemptions_requiring_beneficiary_response(request.user)[:50])

        achievements = []
        owned = []
        recent_activity = []
        if account is not None:
            achievements = [
                {
                    "id": str(grant.pk),
                    "achievement": {
                        "id": str(grant.achievement_id),
                        "code": grant.achievement.code,
                        "name": grant.achievement.name,
                        "badge_label": grant.achievement.badge_label or None,
                    },
                    "granted_at": grant.granted_at,
                }
                for grant in account.achievement_grants.select_related("achievement").order_by(
                    "-granted_at", "id"
                )[:50]
            ]
            owned = list(
                RecognitionRedemption.objects.filter(owner_account=account)
                .select_related("reward")
                .order_by("-created_at", "-id")[:50]
            )
            recent_activity = [
                _ledger_payload(entry)
                for entry in account.ledger_entries.order_by("-created_at", "-id")[:20]
            ]

        received = list(
            RecognitionRedemption.objects.filter(beneficiary_profile=request.user)
            .select_related("reward")
            .order_by("-created_at", "-id")[:50]
        )

        return Response(
            {
                "summary": {
                    "kind": "recognition",
                    "unit": "recognition_credit",
                    "is_currency": False,
                    "available_credits": account.points_balance if account is not None else 0,
                    "pending_credits": account.pending_points if account is not None else 0,
                    "needs_response": bool(incoming),
                },
                "account": _account_payload(account),
                "achievements": achievements,
                "rewards": [_reward_payload(reward) for reward in rewards],
                "incoming": [
                    _redemption_payload(redemption, incoming=True)
                    for redemption in incoming
                ],
                "redemptions": [
                    _redemption_payload(redemption)
                    for redemption in owned
                ],
                "recent_activity": recent_activity,
                "benefits_received": [
                    _redemption_payload(
                        redemption,
                        incoming=(
                            redemption.beneficiary_profile_id == request.user.pk
                            and redemption.status == "requested"
                            and (redemption.fulfillment_snapshot or {}).get("consent_state")
                            == "pending"
                        ),
                    )
                    for redemption in received
                ],
                "capabilities": ["view_history"] if recent_activity else [],
                "links": {"self": reverse("recognition_api:me")},
            }
        )


class RecognitionRewardRedeemAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, reward_id):
        key = str(request.data.get("idempotency_key") or "").strip()
        if not key:
            raise ValidationError(
                {"idempotency_key": "Une clé d'idempotence est obligatoire."}
            )

        account = get_or_create_account(profile=request.user)
        existing = (
            RecognitionRedemption.objects.filter(idempotency_key=key)
            .select_related("reward", "owner_account")
            .first()
        )
        if existing is not None:
            if existing.owner_account_id != account.pk:
                raise ValidationError(
                    {"idempotency_key": "Cette clé d'idempotence n'est pas disponible."}
                )
            return Response(_redemption_payload(existing), status=status.HTTP_200_OK)

        reward = next(
            (
                candidate
                for candidate in active_rewards(owner_account=account)
                if candidate.pk == reward_id
                and bool(getattr(candidate, "recognition_self_eligible", False))
            ),
            None,
        )
        if reward is None:
            raise NotFound("Cette Reward n'est pas disponible pour ce Profil.")

        try:
            redemption = redeem_reward(
                owner_account=account,
                reward=reward,
                idempotency_key=key,
                actor_profile=request.user,
                beneficiary_profile=request.user,
            )
        except DjangoValidationError as exc:
            _raise_service(exc)

        return Response(
            _redemption_payload(redemption),
            status=status.HTTP_201_CREATED,
        )


class RecognitionRedemptionDecisionAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, redemption_id, decision):
        if decision not in {"accept", "decline"}:
            raise NotFound()

        redemption = get_object_or_404(
            redemptions_requiring_beneficiary_response(request.user),
            pk=redemption_id,
        )
        try:
            if decision == "accept":
                redemption = accept_redemption(
                    redemption=redemption,
                    beneficiary_profile=request.user,
                    actor_profile=request.user,
                )
            else:
                redemption = decline_redemption(
                    redemption=redemption,
                    beneficiary_profile=request.user,
                    actor_profile=request.user,
                )
        except DjangoValidationError as exc:
            _raise_service(exc)

        return Response(_redemption_payload(redemption))
