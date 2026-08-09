from rest_framework import serializers

from loyalty.models import LoyaltyAccount, LoyaltyLedgerEntry, LoyaltyProgram, LoyaltyReward, LoyaltyRewardRedemption, LoyaltyTier, MembershipPlan, MembershipSubscription


class LoyaltyTierSerializer(serializers.ModelSerializer):
    class Meta:
        model = LoyaltyTier
        fields = ["id", "name", "code", "threshold_points", "points_multiplier", "benefits", "is_active"]


class MembershipPlanSerializer(serializers.ModelSerializer):
    is_free = serializers.BooleanField(read_only=True)

    class Meta:
        model = MembershipPlan
        fields = ["id", "name", "code", "description", "price", "currency", "duration_days", "points_multiplier", "join_bonus_points", "benefit_promotion", "benefits", "is_active", "is_free"]


class LoyaltyRewardSerializer(serializers.ModelSerializer):
    class Meta:
        model = LoyaltyReward
        fields = ["id", "name", "description", "points_cost", "promotion", "fulfillment_instructions", "max_redemptions_per_member", "starts_at", "ends_at", "is_active"]


class LoyaltyProgramSerializer(serializers.ModelSerializer):
    organization_id = serializers.UUIDField(source="organization.id", read_only=True)
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    tiers = LoyaltyTierSerializer(many=True, read_only=True)
    membership_plans = MembershipPlanSerializer(many=True, read_only=True)
    rewards = LoyaltyRewardSerializer(many=True, read_only=True)

    class Meta:
        model = LoyaltyProgram
        fields = ["id", "organization_id", "organization_name", "name", "description", "points_name", "points_per_order", "points_per_ticket", "points_per_checkin", "is_active", "tiers", "membership_plans", "rewards"]


class MembershipSubscriptionSerializer(serializers.ModelSerializer):
    plan_name = serializers.CharField(source="plan.name", read_only=True)
    organization_name = serializers.CharField(source="program.organization.name", read_only=True)
    benefit_code = serializers.CharField(source="benefit_code.code", read_only=True, allow_null=True)

    class Meta:
        model = MembershipSubscription
        fields = ["id", "program", "organization_name", "plan", "plan_name", "status", "price_amount", "currency", "starts_at", "ends_at", "activation_source", "benefit_code", "requested_at", "activated_at", "cancelled_at", "expired_at"]
        read_only_fields = fields


class LoyaltyLedgerEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = LoyaltyLedgerEntry
        fields = ["id", "kind", "points", "description", "metadata", "created_at"]
        read_only_fields = fields


class LoyaltyAccountSerializer(serializers.ModelSerializer):
    organization_id = serializers.UUIDField(source="program.organization.id", read_only=True)
    organization_name = serializers.CharField(source="program.organization.name", read_only=True)
    current_tier = LoyaltyTierSerializer(read_only=True)
    ledger = LoyaltyLedgerEntrySerializer(source="ledger_entries", many=True, read_only=True)

    class Meta:
        model = LoyaltyAccount
        fields = ["id", "program", "organization_id", "organization_name", "points_balance", "lifetime_earned", "lifetime_redeemed", "current_tier", "joined_at", "ledger"]
        read_only_fields = fields


class LoyaltyRewardRedemptionSerializer(serializers.ModelSerializer):
    reward_name = serializers.CharField(source="reward.name", read_only=True)
    promotion_code = serializers.CharField(source="promotion_code.code", read_only=True, allow_null=True)

    class Meta:
        model = LoyaltyRewardRedemption
        fields = ["id", "reward", "reward_name", "status", "points_cost", "promotion_code", "redeemed_at"]
        read_only_fields = fields
