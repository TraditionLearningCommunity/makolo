from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from django.urls import reverse

from rest_framework import status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from recognition.economy import accept_redemption, decline_redemption, redeem_reward
from recognition.models import RecognitionRedemption, RedemptionStatus
from recognition.selectors import (
    account_for_profile,
    account_for_space,
    active_rewards,
    redemptions_requiring_beneficiary_response,
)
from recognition.services import get_or_create_account
from authorization.constants import PermissionCode
from authorization.services import can
from organizations.models import Organization


PERSONAL_RECOGNITION_LIMIT = 50


def _raise_service(exc):
    if hasattr(exc, "message_dict"):
        raise ValidationError(exc.message_dict) from exc
    raise ValidationError(getattr(exc, "messages", [str(exc)])) from exc


def _reward_payload(reward, *, allow_redeem=None, redeem_url=None):
    self_eligible = bool(getattr(reward, "recognition_self_eligible", False))
    if allow_redeem is None:
        allow_redeem = self_eligible
    capabilities = ["redeem"] if allow_redeem else []
    links = {}
    if allow_redeem:
        links["redeem"] = redeem_url or reverse(
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
        "validity": {
            "state": "available",
            "valid_from": reward.valid_from,
            "valid_until": reward.valid_until,
        },
        "beneficiary_allowed": bool(reward.beneficiary_allowed),
        "acceptance_required": bool(reward.acceptance_required),
        "self_eligible": self_eligible,
        "requires_other_beneficiary": bool(
            getattr(reward, "recognition_requires_other_beneficiary", False)
        ),
        "capabilities": capabilities,
        "links": links,
    }


def _redemption_payload(redemption, *, incoming=False, decision_links=None):
    consent_state = (redemption.fulfillment_snapshot or {}).get("consent_state")
    capabilities = []
    links = {}
    if incoming and redemption.status == "requested" and consent_state == "pending":
        capabilities = ["accept", "decline"]
        links = decision_links or {
            "accept": reverse(
                "recognition_api:redemption-decision",
                kwargs={"redemption_id": redemption.pk, "decision": "accept"},
            ),
            "decline": reverse(
                "recognition_api:redemption-decision",
                kwargs={"redemption_id": redemption.pk, "decision": "decline"},
            ),
        }
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
        rewards = (
            active_rewards(owner_account=account)[:PERSONAL_RECOGNITION_LIMIT]
            if account is not None
            else []
        )
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

        response = Response(
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
        response["Cache-Control"] = "private, no-store"
        return response


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
            response = Response(
                _redemption_payload(existing),
                status=status.HTTP_200_OK,
            )
            response["Cache-Control"] = "private, no-store"
            return response

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

        response = Response(
            _redemption_payload(redemption),
            status=status.HTTP_201_CREATED,
        )
        response["Cache-Control"] = "private, no-store"
        return response


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

        response = Response(_redemption_payload(redemption))
        response["Cache-Control"] = "private, no-store"
        return response



def _space_for_recognition(actor, space_id, *, spend=False):
    space = Organization.objects.filter(pk=space_id).first()
    if space is None:
        raise NotFound()
    code = PermissionCode.SPACE_RECOGNITION_SPEND if spend else PermissionCode.SPACE_RECOGNITION_VIEW
    allowed = can(actor, code, space=space)
    if not allowed and not spend:
        allowed = can(actor, PermissionCode.SPACE_RECOGNITION_SPEND, space=space)
    if not allowed:
        raise NotFound()
    return space


class SpaceRecognitionAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, space_id):
        space = _space_for_recognition(request.user, space_id)
        account = account_for_space(space)
        can_spend = can(request.user, PermissionCode.SPACE_RECOGNITION_SPEND, space=space)
        rewards = active_rewards(owner_account=account)[:PERSONAL_RECOGNITION_LIMIT] if account else []
        incoming = []
        owned = []
        received = []
        recent_activity = []
        achievements = []

        if account:
            owned = list(
                RecognitionRedemption.objects.filter(owner_account=account)
                .select_related("reward")
                .order_by("-created_at", "-id")[:50]
            )
            recent_activity = [
                _ledger_payload(entry)
                for entry in account.ledger_entries.order_by("-created_at", "-id")[:20]
            ]
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
                for grant in account.achievement_grants.select_related("achievement").order_by("-granted_at", "id")[:50]
            ]

        if can_spend:
            incoming = list(
                RecognitionRedemption.objects.filter(
                    beneficiary_space=space,
                    status=RedemptionStatus.REQUESTED,
                    fulfillment_snapshot__consent_state="pending",
                )
                .select_related("reward")
                .order_by("created_at", "id")[:50]
            )

        received = list(
            RecognitionRedemption.objects.filter(beneficiary_space=space)
            .select_related("reward")
            .order_by("-created_at", "-id")[:50]
        )

        response = Response({
            "space": {"id": str(space.pk), "slug": space.slug, "name": space.name},
            "summary": {
                "kind": "recognition",
                "unit": "recognition_credit",
                "is_currency": False,
                "available_credits": account.points_balance if account else 0,
                "pending_credits": account.pending_points if account else 0,
                "needs_response": bool(incoming),
            },
            "account": _account_payload(account),
            "achievements": achievements,
            "rewards": [
                _reward_payload(
                    reward,
                    allow_redeem=can_spend,
                    redeem_url=f"/api/v1/recognition/spaces/{space.pk}/rewards/{reward.pk}/redeem/",
                )
                for reward in rewards
            ],
            "incoming": [
                _redemption_payload(
                    row,
                    incoming=True,
                    decision_links={
                        "accept": f"/api/v1/recognition/spaces/{space.pk}/redemptions/{row.pk}/accept/",
                        "decline": f"/api/v1/recognition/spaces/{space.pk}/redemptions/{row.pk}/decline/",
                    },
                )
                for row in incoming
            ],
            "redemptions": [_redemption_payload(row) for row in owned],
            "recent_activity": recent_activity,
            "benefits_received": [_redemption_payload(row) for row in received],
            "capabilities": ["view"] + (["spend", "respond"] if can_spend else []),
            "links": {"self": f"/api/v1/recognition/spaces/{space.pk}/"},
        })
        response["Cache-Control"] = "private, no-store"
        return response


class SpaceRecognitionRewardRedeemAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, space_id, reward_id):
        space = _space_for_recognition(request.user, space_id, spend=True)
        key = str(request.data.get("idempotency_key") or "").strip()
        if not key:
            raise ValidationError({"idempotency_key": "Une clé d'idempotence est obligatoire."})

        account = get_or_create_account(space=space)
        existing = (
            RecognitionRedemption.objects.filter(idempotency_key=key)
            .select_related("owner_account", "reward")
            .first()
        )
        if existing is not None:
            if existing.owner_account_id != account.pk:
                raise ValidationError({"idempotency_key": "Cette clé d'idempotence n'est pas disponible."})
            response = Response(_redemption_payload(existing))
            response["Cache-Control"] = "private, no-store"
            return response

        reward = next(
            (row for row in active_rewards(owner_account=account) if row.pk == reward_id),
            None,
        )
        if reward is None:
            raise NotFound("Cette Reward n'est pas disponible pour cet Espace.")

        beneficiary_profile = None
        beneficiary_space = space
        profile_id = request.data.get("beneficiary_profile_id")
        target_space_id = request.data.get("beneficiary_space_id")
        if profile_id or target_space_id:
            if not reward.beneficiary_allowed or (profile_id and target_space_id):
                raise ValidationError({"beneficiary": "Ce bénéficiaire n'est pas disponible pour cette Reward."})
            if profile_id:
                beneficiary_profile = get_object_or_404(get_user_model(), pk=profile_id)
                beneficiary_space = None
            else:
                beneficiary_space = get_object_or_404(Organization, pk=target_space_id)

        try:
            redemption = redeem_reward(
                owner_account=account,
                reward=reward,
                idempotency_key=key,
                actor_profile=request.user,
                beneficiary_profile=beneficiary_profile,
                beneficiary_space=beneficiary_space,
            )
        except DjangoValidationError as exc:
            _raise_service(exc)

        response = Response(_redemption_payload(redemption), status=status.HTTP_201_CREATED)
        response["Cache-Control"] = "private, no-store"
        return response


class SpaceRecognitionRedemptionDecisionAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, space_id, redemption_id, decision):
        space = _space_for_recognition(request.user, space_id, spend=True)
        if decision not in {"accept", "decline"}:
            raise NotFound()

        redemption = get_object_or_404(
            RecognitionRedemption.objects.select_related("reward").filter(
                beneficiary_space=space,
                status=RedemptionStatus.REQUESTED,
                fulfillment_snapshot__consent_state="pending",
            ),
            pk=redemption_id,
        )
        try:
            if decision == "accept":
                redemption = accept_redemption(
                    redemption=redemption,
                    beneficiary_space=space,
                    actor_profile=request.user,
                )
            else:
                redemption = decline_redemption(
                    redemption=redemption,
                    beneficiary_space=space,
                    actor_profile=request.user,
                )
        except DjangoValidationError as exc:
            _raise_service(exc)

        response = Response(_redemption_payload(redemption))
        response["Cache-Control"] = "private, no-store"
        return response
