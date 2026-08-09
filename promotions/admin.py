from django.contrib import admin

from .models import Promotion, PromotionCode, PromotionRedemption


class PromotionCodeInline(admin.TabularInline):
    model = PromotionCode
    extra = 0
    fields = ("code", "label", "is_private", "is_active", "max_redemptions", "crm_campaign")


@admin.register(Promotion)
class PromotionAdmin(admin.ModelAdmin):
    list_display = ("name", "organization", "event", "discount_type", "discount_value", "currency", "is_active", "updated_at")
    list_filter = ("organization", "discount_type", "is_active")
    search_fields = ("name", "description", "organization__name")
    filter_horizontal = ("eligible_ticket_types",)
    inlines = [PromotionCodeInline]


@admin.register(PromotionCode)
class PromotionCodeAdmin(admin.ModelAdmin):
    list_display = ("code", "promotion", "is_private", "is_active", "max_redemptions", "crm_campaign", "updated_at")
    list_filter = ("promotion__organization", "is_private", "is_active")
    search_fields = ("code", "label", "promotion__name")


@admin.register(PromotionRedemption)
class PromotionRedemptionAdmin(admin.ModelAdmin):
    list_display = ("code", "order", "status", "discount_amount", "final_amount", "currency", "reserved_at")
    list_filter = ("status", "promotion__organization", "currency")
    search_fields = ("code__code", "order__reference", "customer_email")
    readonly_fields = [field.name for field in PromotionRedemption._meta.fields]

    def has_add_permission(self, request):
        return False
