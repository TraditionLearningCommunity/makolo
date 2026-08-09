from django.contrib import admin

from .models import LoyaltyAccount, LoyaltyLedgerEntry, LoyaltyProgram, LoyaltyReward, LoyaltyRewardRedemption, LoyaltyTier, MembershipPlan, MembershipSubscription


@admin.register(LoyaltyProgram)
class LoyaltyProgramAdmin(admin.ModelAdmin):
    list_display = ("organization", "name", "is_active", "points_per_order", "points_per_ticket", "points_per_checkin")
    list_filter = ("is_active",)
    search_fields = ("organization__name", "name")
    autocomplete_fields = ("organization", "created_by")


@admin.register(LoyaltyTier)
class LoyaltyTierAdmin(admin.ModelAdmin):
    list_display = ("program", "name", "code", "threshold_points", "points_multiplier", "is_active")
    list_filter = ("is_active",)
    search_fields = ("program__organization__name", "name", "code")
    autocomplete_fields = ("program",)


@admin.register(MembershipPlan)
class MembershipPlanAdmin(admin.ModelAdmin):
    list_display = ("program", "name", "price", "currency", "duration_days", "points_multiplier", "is_active")
    list_filter = ("is_active", "currency")
    search_fields = ("program__organization__name", "name", "code")
    autocomplete_fields = ("program", "benefit_promotion", "created_by")


@admin.register(MembershipSubscription)
class MembershipSubscriptionAdmin(admin.ModelAdmin):
    list_display = ("user", "plan", "status", "price_amount", "currency", "starts_at", "ends_at")
    list_filter = ("status", "currency")
    search_fields = ("user__email", "user__username", "plan__name", "program__organization__name")
    autocomplete_fields = ("program", "plan", "user", "activated_by", "benefit_code")
    readonly_fields = ("requested_at", "activated_at", "cancelled_at", "expired_at", "updated_at")


@admin.register(LoyaltyAccount)
class LoyaltyAccountAdmin(admin.ModelAdmin):
    list_display = ("user", "program", "points_balance", "lifetime_earned", "lifetime_redeemed", "current_tier")
    search_fields = ("user__email", "user__username", "program__organization__name")
    autocomplete_fields = ("program", "user", "current_tier")
    readonly_fields = ("points_balance", "lifetime_earned", "lifetime_redeemed", "joined_at", "updated_at")


@admin.register(LoyaltyReward)
class LoyaltyRewardAdmin(admin.ModelAdmin):
    list_display = ("program", "name", "points_cost", "is_active", "starts_at", "ends_at")
    list_filter = ("is_active",)
    search_fields = ("program__organization__name", "name")
    autocomplete_fields = ("program", "promotion", "created_by")


@admin.register(LoyaltyRewardRedemption)
class LoyaltyRewardRedemptionAdmin(admin.ModelAdmin):
    list_display = ("redeemed_at", "user", "reward", "points_cost", "status", "promotion_code")
    list_filter = ("status",)
    search_fields = ("user__email", "reward__name")
    autocomplete_fields = ("account", "reward", "user", "promotion_code")
    readonly_fields = ("account", "reward", "user", "status", "points_cost", "promotion_code", "redeemed_at", "cancelled_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(LoyaltyLedgerEntry)
class LoyaltyLedgerEntryAdmin(admin.ModelAdmin):
    list_display = ("created_at", "account", "kind", "points", "description")
    list_filter = ("kind",)
    search_fields = ("account__user__email", "account__program__organization__name", "description", "idempotency_key")
    autocomplete_fields = ("account", "order", "ticket", "subscription", "reward_redemption", "created_by")
    readonly_fields = ("account", "kind", "points", "description", "idempotency_key", "order", "ticket", "subscription", "reward_redemption", "created_by", "metadata", "created_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
