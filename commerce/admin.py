from django.contrib import admin

from .models import CommerceOrder, CommerceOrderItem, Offer


@admin.register(Offer)
class OfferAdmin(admin.ModelAdmin):
    list_display = ("name", "activity", "occurrence", "unit_price", "currency", "payment_mode", "capacity_pool", "status")
    list_filter = ("status", "payment_mode", "currency", "activity")
    search_fields = ("name", "activity__title", "source_key")
    list_select_related = ("activity", "occurrence", "capacity_pool")
    readonly_fields = ("created_at", "updated_at")


class CommerceOrderItemInline(admin.TabularInline):
    model = CommerceOrderItem
    extra = 0
    can_delete = False
    readonly_fields = ("offer", "beneficiary", "quantity", "label_snapshot", "unit_price", "line_subtotal", "discount_total", "line_total", "capacity_reservation", "created_at")


@admin.register(CommerceOrder)
class CommerceOrderAdmin(admin.ModelAdmin):
    list_display = ("reference", "journey", "buyer", "payee_space", "subtotal", "discount_total", "total", "currency", "payment_mode", "status")
    list_filter = ("status", "currency", "payment_mode", "payee_space")
    search_fields = ("reference", "buyer__email", "journey__beneficiary__email", "source_key")
    list_select_related = ("journey", "buyer", "payee_space")
    readonly_fields = ("reference", "journey", "buyer", "payee_space", "status", "currency", "payment_mode", "subtotal", "discount_total", "total", "expires_at", "confirmed_at", "cancelled_at", "idempotency_key", "source_key", "created_at", "updated_at")
    inlines = (CommerceOrderItemInline,)


@admin.register(CommerceOrderItem)
class CommerceOrderItemAdmin(admin.ModelAdmin):
    list_display = ("order", "label_snapshot", "offer", "quantity", "unit_price", "line_total", "capacity_reservation")
    list_select_related = ("order", "offer", "beneficiary", "capacity_reservation")
    readonly_fields = ("order", "offer", "beneficiary", "quantity", "label_snapshot", "unit_price", "line_subtotal", "discount_total", "line_total", "capacity_reservation", "created_at")
