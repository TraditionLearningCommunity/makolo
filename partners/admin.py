from django.contrib import admin

from .models import (
    AffiliateCampaign,
    Partner,
    PartnerCommission,
    PartnerPayout,
    ReferralAttribution,
    ReferralCode,
    ReferralVisit,
)


@admin.register(Partner)
class PartnerAdmin(admin.ModelAdmin):
    list_display = ("name", "organization", "kind", "status", "user", "created_at")
    list_filter = ("kind", "status", "organization")
    search_fields = ("name", "email", "user__email", "organization__name")


@admin.register(AffiliateCampaign)
class AffiliateCampaignAdmin(admin.ModelAdmin):
    list_display = ("name", "organization", "event", "status", "commission_type", "commission_value", "created_at")
    list_filter = ("status", "commission_type", "organization")
    search_fields = ("name", "event__title", "organization__name")


@admin.register(ReferralCode)
class ReferralCodeAdmin(admin.ModelAdmin):
    list_display = ("code", "partner", "campaign", "is_active", "created_at")
    list_filter = ("is_active", "campaign__organization")
    search_fields = ("code", "partner__name", "campaign__name")


@admin.register(ReferralVisit)
class ReferralVisitAdmin(admin.ModelAdmin):
    list_display = ("referral_code", "visitor_id", "referrer_domain", "created_at")
    search_fields = ("referral_code__code", "referrer_domain")
    readonly_fields = ("referral_code", "visitor_id", "landing_path", "referrer_domain", "created_at")


@admin.register(ReferralAttribution)
class ReferralAttributionAdmin(admin.ModelAdmin):
    list_display = ("order", "partner", "campaign", "status", "attributed_at", "confirmed_at")
    list_filter = ("status", "campaign__organization")
    search_fields = ("order__reference", "partner__name", "referral_code__code")
    readonly_fields = ("order", "referral_code", "campaign", "partner", "visitor_id", "attributed_at", "confirmed_at", "reversed_at")


@admin.register(PartnerCommission)
class PartnerCommissionAdmin(admin.ModelAdmin):
    list_display = ("partner", "order", "amount", "currency", "status", "earned_at", "paid_at")
    list_filter = ("status", "currency", "campaign__organization")
    search_fields = ("partner__name", "order__reference", "campaign__name")
    readonly_fields = ("attribution", "partner", "campaign", "order", "amount", "currency", "commission_type", "commission_value", "earned_at", "reversed_at", "paid_at")


@admin.register(PartnerPayout)
class PartnerPayoutAdmin(admin.ModelAdmin):
    list_display = ("partner", "amount", "currency", "status", "reference", "created_at", "paid_at")
    list_filter = ("status", "currency", "organization")
    search_fields = ("partner__name", "reference", "organization__name")
