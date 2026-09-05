from django.contrib import admin

from authorization.services import has_platform_authority

from .models import CommerceOrder, CommerceOrderItem, Offer


@admin.register(Offer)
class OfferAdmin(admin.ModelAdmin):
    list_display = ("name", "activity", "occurrence", "unit_price", "currency", "payment_mode", "capacity_pool", "status")
    list_filter = ("status", "payment_mode", "currency", "activity")
    search_fields = ("name", "activity__title", "source_key")
    list_select_related = ("activity", "occurrence", "capacity_pool")
    readonly_fields = ("created_at", "updated_at")

    def _can_write(self, request):
        return bool(request.user.is_authenticated and has_platform_authority(request.user))

    def has_add_permission(self, request):
        return self._can_write(request) and super().has_add_permission(request)

    def has_change_permission(self, request, obj=None):
        return self._can_write(request) and super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return self._can_write(request) and super().has_delete_permission(request, obj)


class CommerceOrderItemInline(admin.TabularInline):
    model = CommerceOrderItem
    extra = 0
    can_delete = False
    readonly_fields = ("offer", "beneficiary", "external_beneficiary", "quantity", "label_snapshot", "unit_price", "line_subtotal", "discount_total", "line_total", "capacity_reservation", "created_at")

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(CommerceOrder)
class CommerceOrderAdmin(admin.ModelAdmin):
    list_display = ("reference", "journey", "buyer", "payee_space", "subtotal", "discount_total", "total", "currency", "payment_mode", "status")
    list_filter = ("status", "currency", "payment_mode", "payee_space")
    search_fields = ("reference", "buyer__email", "journey__beneficiary__email", "source_key")
    list_select_related = ("journey", "buyer", "payee_space")
    readonly_fields = ("reference", "journey", "buyer", "payee_space", "payee_profile", "status", "currency", "payment_mode", "subtotal", "discount_total", "total", "pricing_policy", "expected_payee_amount", "makolo_amount", "financial_snapshot", "expires_at", "confirmed_at", "cancelled_at", "idempotency_key", "source_key", "created_at", "updated_at")
    inlines = (CommerceOrderItemInline,)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(CommerceOrderItem)
class CommerceOrderItemAdmin(admin.ModelAdmin):
    list_display = ("order", "label_snapshot", "offer", "quantity", "unit_price", "line_total", "capacity_reservation")
    list_select_related = ("order", "offer", "beneficiary", "capacity_reservation")
    readonly_fields = ("order", "offer", "beneficiary", "external_beneficiary", "quantity", "label_snapshot", "unit_price", "line_subtotal", "discount_total", "line_total", "capacity_reservation", "created_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
