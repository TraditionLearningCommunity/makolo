from django.contrib import admin

from .canonical_models import CommercePromotionRedemption, PromotionOffer, PromotionTargeting


@admin.register(PromotionTargeting)
class PromotionTargetingAdmin(admin.ModelAdmin):
    list_display = ("promotion", "activity", "audience", "updated_at")
    list_filter = ("promotion__organization",)
    search_fields = ("promotion__name", "activity__title", "audience__name")
    raw_id_fields = ("promotion", "activity", "audience")


@admin.register(PromotionOffer)
class PromotionOfferAdmin(admin.ModelAdmin):
    list_display = ("promotion", "offer", "source", "created_at")
    list_filter = ("source", "promotion__organization")
    search_fields = ("promotion__name", "offer__name")
    raw_id_fields = ("promotion", "offer")


@admin.register(CommercePromotionRedemption)
class CommercePromotionRedemptionAdmin(admin.ModelAdmin):
    list_display = ("promotion", "code", "commerce_order", "status", "currency", "reserved_at")
    list_filter = ("status", "currency")
    search_fields = ("promotion__name", "customer_email")
    raw_id_fields = ("commerce_order", "buyer")
    readonly_fields = (
        "promotion",
        "code",
        "commerce_order",
        "buyer",
        "customer_email",
        "subtotal_amount",
        "eligible_amount",
        "discount_amount",
        "final_amount",
        "currency",
        "reserved_at",
        "confirmed_at",
        "reversed_at",
    )
