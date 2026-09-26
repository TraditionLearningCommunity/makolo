from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import permissions, serializers, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from organizations.models import Organization
from organizations.permissions import organization_has_public_profile
from promotions.models import Promotion

from loyalty.models import LoyaltyAccount, LoyaltyLedgerEntry, LoyaltyProgram, LoyaltyReward, LoyaltyTier, MembershipPlan, MembershipSubscription
from loyalty.permissions import user_can_manage_loyalty_strategy, user_can_view_loyalty_workspace
from loyalty.selectors import get_accounts_visible_to, get_programs_visible_to, get_subscriptions_visible_to, personal_rewards_available_to
from loyalty.services import activate_membership, adjust_points, cancel_membership, redeem_reward, request_membership

from .serializers import LoyaltyAccountSerializer, LoyaltyProgramSerializer, LoyaltyRewardRedemptionSerializer, LoyaltyRewardSerializer, LoyaltyTierSerializer, MembershipPlanSerializer, MembershipSubscriptionSerializer


PERSONAL_LOYALTY_LIMIT = 50
PERSONAL_LOYALTY_RECENT_ACTIVITY_LIMIT = 20


class MembershipJoinRequestSerializer(serializers.Serializer):
    plan_id = serializers.UUIDField()


class ProgramCreateSerializer(serializers.Serializer):
    organization_id = serializers.UUIDField()
    name = serializers.CharField(max_length=160, default="Programme fidélité")
    description = serializers.CharField(required=False, allow_blank=True, default="")
    points_name = serializers.CharField(max_length=40, default="points")
    points_per_order = serializers.IntegerField(min_value=0, default=10)
    points_per_ticket = serializers.IntegerField(min_value=0, default=5)
    points_per_checkin = serializers.IntegerField(min_value=0, default=20)
    is_active = serializers.BooleanField(default=True)


class TierCreateSerializer(serializers.Serializer):
    program_id = serializers.UUIDField()
    name = serializers.CharField(max_length=120)
    code = serializers.CharField(max_length=40)
    threshold_points = serializers.IntegerField(min_value=0)
    points_multiplier = serializers.DecimalField(max_digits=5, decimal_places=2, default="1.00")
    benefits = serializers.CharField(required=False, allow_blank=True, default="")
    is_active = serializers.BooleanField(default=True)


class PlanCreateSerializer(serializers.Serializer):
    program_id = serializers.UUIDField()
    name = serializers.CharField(max_length=160)
    code = serializers.CharField(max_length=40)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    price = serializers.DecimalField(max_digits=12, decimal_places=2, default="0.00")
    currency = serializers.CharField(max_length=3, default="USD")
    duration_days = serializers.IntegerField(min_value=1, max_value=3650, default=365)
    points_multiplier = serializers.DecimalField(max_digits=5, decimal_places=2, default="1.00")
    join_bonus_points = serializers.IntegerField(min_value=0, default=0)
    benefit_promotion_id = serializers.UUIDField(required=False, allow_null=True)
    benefits = serializers.CharField(required=False, allow_blank=True, default="")
    is_active = serializers.BooleanField(default=True)


class RewardCreateSerializer(serializers.Serializer):
    program_id = serializers.UUIDField()
    name = serializers.CharField(max_length=160)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    points_cost = serializers.IntegerField(min_value=1)
    promotion_id = serializers.UUIDField(required=False, allow_null=True)
    fulfillment_instructions = serializers.CharField(required=False, allow_blank=True, default="")
    max_redemptions_per_member = serializers.IntegerField(min_value=1, max_value=100, default=1)
    is_active = serializers.BooleanField(default=True)


class PointsAdjustmentSerializer(serializers.Serializer):
    points = serializers.IntegerField()
    reason = serializers.CharField(max_length=255)

    def validate_points(self, value):
        if value == 0:
            raise serializers.ValidationError("L'ajustement ne peut pas être nul.")
        return value


def _raise_service(exc):
    if isinstance(exc, DjangoPermissionDenied):
        raise PermissionDenied(str(exc)) from exc
    if hasattr(exc, "message_dict"):
        raise ValidationError(exc.message_dict) from exc
    raise ValidationError(getattr(exc, "messages", [str(exc)])) from exc


def _personal_loyalty_account_payload(account):
    tier = account.current_tier
    recent = getattr(account, "_personal_recent_ledger", None)
    if recent is None:
        recent = list(
            account.ledger_entries.order_by("-created_at", "-id")[
                :PERSONAL_LOYALTY_RECENT_ACTIVITY_LIMIT
            ]
        )
    return {
        "id": str(account.pk),
        "program": str(account.program_id),
        "organization_id": str(account.program.organization_id),
        "organization_name": account.program.organization.name,
        "program_name": account.program.name,
        "points_name": account.program.points_name,
        "points_balance": account.points_balance,
        "lifetime_earned": account.lifetime_earned,
        "lifetime_redeemed": account.lifetime_redeemed,
        "current_tier": (
            {
                "id": str(tier.pk),
                "name": tier.name,
                "code": tier.code,
            }
            if tier is not None
            else None
        ),
        "joined_at": account.joined_at,
        "recent_activity": [
            {
                "id": str(entry.pk),
                "kind": entry.kind,
                "points_delta": entry.points,
                "description": entry.description,
                "created_at": entry.created_at,
            }
            for entry in recent
        ],
    }


def _personal_loyalty_reward_payload(reward):
    return {
        "id": str(reward.pk),
        "program": str(reward.program_id),
        "organization": {
            "id": str(reward.program.organization_id),
            "name": reward.program.organization.name,
        },
        "name": reward.name,
        "description": reward.description or None,
        "points_cost": reward.points_cost,
        "points_name": reward.program.points_name,
        "validity": {
            "state": "available",
            "starts_at": reward.starts_at,
            "ends_at": reward.ends_at,
        },
        "capabilities": ["redeem"],
        "links": {
            "redeem": f"/api/v1/loyalty/rewards/{reward.pk}/redeem/",
        },
    }


class MyLoyaltyAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        account_queryset = (
            get_accounts_visible_to(request.user)
            .filter(user=request.user)
            .select_related("program__organization", "current_tier")
            .order_by("program__organization__name", "id")
        )
        subscription_queryset = (
            get_subscriptions_visible_to(request.user)
            .filter(user=request.user)
            .select_related("program__organization", "plan", "benefit_code")
            .order_by("program__organization__name", "-requested_at", "id")
        )
        program_count = account_queryset.values("program_id").distinct().count()
        membership_count = subscription_queryset.count()

        recent_ledger = LoyaltyLedgerEntry.objects.order_by(
            "-created_at",
            "-id",
        )[:PERSONAL_LOYALTY_RECENT_ACTIVITY_LIMIT]
        accounts = list(
            account_queryset.prefetch_related(
                Prefetch(
                    "ledger_entries",
                    queryset=recent_ledger,
                    to_attr="_personal_recent_ledger",
                )
            )[:PERSONAL_LOYALTY_LIMIT]
        )
        subscriptions = list(subscription_queryset[:PERSONAL_LOYALTY_LIMIT])
        redemptions = list(
            request.user.loyalty_reward_redemptions.select_related(
                "reward__program__organization",
                "promotion_code",
            ).order_by("-redeemed_at", "id")[:PERSONAL_LOYALTY_LIMIT]
        )
        available_rewards = personal_rewards_available_to(
            request.user,
            at=timezone.now(),
        )[:PERSONAL_LOYALTY_LIMIT]
        response = Response({
            "accounts": [
                _personal_loyalty_account_payload(account)
                for account in accounts
            ],
            "memberships": MembershipSubscriptionSerializer(
                subscriptions,
                many=True,
            ).data,
            "rewards": LoyaltyRewardRedemptionSerializer(
                redemptions,
                many=True,
            ).data,
            "available_rewards": [
                _personal_loyalty_reward_payload(reward)
                for reward in available_rewards
            ],
            "summary": {
                "kind": "loyalty",
                "program_count": program_count,
                "membership_count": membership_count,
                "has_available_rewards": bool(available_rewards),
                "aggregate_points": None,
            },
            "limits": {
                "accounts": PERSONAL_LOYALTY_LIMIT,
                "memberships": PERSONAL_LOYALTY_LIMIT,
                "rewards": PERSONAL_LOYALTY_LIMIT,
                "recent_activity_per_account": PERSONAL_LOYALTY_RECENT_ACTIVITY_LIMIT,
            },
            "links": {"self": "/api/v1/loyalty/me/"},
        })
        response["Cache-Control"] = "private, no-store"
        return response


class OrganizationProgramAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, slug):
        organization = get_object_or_404(Organization, slug=slug)
        can_workspace = request.user.is_authenticated and user_can_view_loyalty_workspace(request.user, organization)
        if not organization_has_public_profile(organization) and not can_workspace:
            raise PermissionDenied("Ce programme n'est pas public.")
        program = get_object_or_404(LoyaltyProgram.objects.prefetch_related("tiers", "membership_plans", "rewards"), organization=organization, is_active=True)
        payload = {"program": LoyaltyProgramSerializer(program).data}
        if request.user.is_authenticated:
            account = LoyaltyAccount.objects.filter(
                program=program,
                user=request.user,
            ).select_related("program__organization", "current_tier").first()
            membership = MembershipSubscription.objects.filter(
                program=program,
                user=request.user,
                status__in=["pending", "active"],
            ).select_related("plan", "benefit_code").first()
            payload["my_account"] = (
                _personal_loyalty_account_payload(account)
                if account
                else None
            )
            payload["my_membership"] = (
                MembershipSubscriptionSerializer(membership).data
                if membership
                else None
            )
        response = Response(payload)
        if request.user.is_authenticated:
            response["Cache-Control"] = "private, no-store"
        return response


class MembershipJoinAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = MembershipJoinRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        plan = get_object_or_404(MembershipPlan, pk=serializer.validated_data["plan_id"])
        try:
            subscription = request_membership(user=request.user, plan=plan)
        except (DjangoPermissionDenied, DjangoValidationError) as exc:
            _raise_service(exc)
        return Response(MembershipSubscriptionSerializer(subscription).data, status=status.HTTP_201_CREATED)


class MembershipCancelAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        subscription = get_object_or_404(get_subscriptions_visible_to(request.user), pk=pk)
        try:
            subscription = cancel_membership(subscription=subscription, actor=request.user)
        except (DjangoPermissionDenied, DjangoValidationError) as exc:
            _raise_service(exc)
        return Response(MembershipSubscriptionSerializer(subscription).data)


class MembershipActivateAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        subscription = get_object_or_404(get_subscriptions_visible_to(request.user), pk=pk)
        try:
            subscription = activate_membership(subscription=subscription, actor=request.user)
        except (DjangoPermissionDenied, DjangoValidationError) as exc:
            _raise_service(exc)
        return Response(MembershipSubscriptionSerializer(subscription).data)


class RewardRedeemAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        idempotency_key = str(request.data.get("idempotency_key") or "").strip()
        if not idempotency_key:
            raise ValidationError(
                {"idempotency_key": "Une clé d'idempotence est obligatoire."}
            )
        if len(idempotency_key) > 120:
            raise ValidationError(
                {"idempotency_key": "Cette clé ne peut pas dépasser 120 caractères."}
            )

        reward = get_object_or_404(
            LoyaltyReward.objects.filter(
                program__accounts__user=request.user,
                is_active=True,
            ).distinct(),
            pk=pk,
        )
        try:
            redemption = redeem_reward(
                user=request.user,
                reward=reward,
                idempotency_key=idempotency_key,
            )
        except (DjangoPermissionDenied, DjangoValidationError) as exc:
            _raise_service(exc)
        response = Response(
            LoyaltyRewardRedemptionSerializer(redemption).data,
            status=status.HTTP_201_CREATED,
        )
        response["Cache-Control"] = "private, no-store"
        return response


class ProgramListCreateAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        queryset = get_programs_visible_to(request.user).prefetch_related("tiers", "membership_plans", "rewards")
        organization = str(request.query_params.get("organization") or "").strip()
        if organization:
            try:
                import uuid
                uuid.UUID(organization)
            except (ValueError, TypeError, AttributeError):
                queryset = queryset.filter(organization__slug=organization)
            else:
                queryset = queryset.filter(organization_id=organization)
        return Response(LoyaltyProgramSerializer(queryset, many=True).data)

    def post(self, request):
        serializer = ProgramCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        organization = get_object_or_404(Organization, pk=data.pop("organization_id"))
        if not user_can_manage_loyalty_strategy(request.user, organization):
            raise PermissionDenied("Un rôle Marketing, Owner ou Admin est requis.")
        if LoyaltyProgram.objects.filter(organization=organization).exists():
            raise ValidationError({"organization_id": "Cette organisation possède déjà un programme fidélité."})
        program = LoyaltyProgram(organization=organization, created_by=request.user, **data)
        program.full_clean()
        program.save()
        return Response(LoyaltyProgramSerializer(program).data, status=status.HTTP_201_CREATED)


class TierCreateAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = TierCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        program = get_object_or_404(get_programs_visible_to(request.user), pk=data.pop("program_id"))
        if not user_can_manage_loyalty_strategy(request.user, program.organization):
            raise PermissionDenied()
        tier = LoyaltyTier(program=program, **data)
        tier.full_clean()
        tier.save()
        return Response(LoyaltyTierSerializer(tier).data, status=status.HTTP_201_CREATED)


class PlanCreateAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = PlanCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        program = get_object_or_404(get_programs_visible_to(request.user), pk=data.pop("program_id"))
        if not user_can_manage_loyalty_strategy(request.user, program.organization):
            raise PermissionDenied()
        promotion_id = data.pop("benefit_promotion_id", None)
        promotion = get_object_or_404(Promotion, pk=promotion_id) if promotion_id else None
        plan = MembershipPlan(program=program, created_by=request.user, benefit_promotion=promotion, **data)
        plan.full_clean()
        plan.save()
        return Response(MembershipPlanSerializer(plan).data, status=status.HTTP_201_CREATED)


class RewardCreateAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = RewardCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        program = get_object_or_404(get_programs_visible_to(request.user), pk=data.pop("program_id"))
        if not user_can_manage_loyalty_strategy(request.user, program.organization):
            raise PermissionDenied()
        promotion_id = data.pop("promotion_id", None)
        promotion = get_object_or_404(Promotion, pk=promotion_id) if promotion_id else None
        reward = LoyaltyReward(program=program, created_by=request.user, promotion=promotion, **data)
        reward.full_clean()
        reward.save()
        return Response(LoyaltyRewardSerializer(reward).data, status=status.HTTP_201_CREATED)


class AccountAdjustAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        serializer = PointsAdjustmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        account = get_object_or_404(get_accounts_visible_to(request.user), pk=pk)
        try:
            adjust_points(actor=request.user, account=account, **serializer.validated_data)
        except (DjangoPermissionDenied, DjangoValidationError) as exc:
            _raise_service(exc)
        account.refresh_from_db()
        return Response(LoyaltyAccountSerializer(account).data)
