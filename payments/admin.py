from django.contrib import admin

from .models import Payment, PaymentEvent, PaymentEvidence, PaymentObligation, Refund


class RefundInline(admin.TabularInline):
    model = Refund
    extra = 0
    can_delete = False
    readonly_fields = (
        "reference", "status", "amount", "currency", "reason", "provider_reference",
        "requested_by", "processed_at", "created_at",
    )

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(PaymentObligation)
class PaymentObligationAdmin(admin.ModelAdmin):
    list_display = ("label", "journey", "reason", "processing_mode", "status", "amount", "currency", "due_at")
    list_filter = ("reason", "processing_mode", "status", "currency")
    search_fields = ("label", "source_key", "external_payee_name", "journey__id", "commerce_order__reference")
    readonly_fields = [field.name for field in PaymentObligation._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(PaymentEvidence)
class PaymentEvidenceAdmin(admin.ModelAdmin):
    list_display = ("obligation", "status", "paid_at", "submitted_by", "verified_by", "verified_at")
    list_filter = ("status", "paid_at", "verified_at")
    search_fields = ("obligation__label", "external_reference", "artifact__title")
    readonly_fields = [field.name for field in PaymentEvidence._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("reference", "order", "commerce_order", "obligation", "provider", "method", "status", "amount", "currency", "created_at")
    list_filter = ("provider", "method", "status", "currency", "created_at")
    search_fields = (
        "reference", "order__reference", "commerce_order__reference", "obligation__label",
        "provider_reference", "payer_name", "payer_email", "payer_phone",
    )
    readonly_fields = [field.name for field in Payment._meta.fields]
    inlines = [RefundInline]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Refund)
class RefundAdmin(admin.ModelAdmin):
    list_display = ("reference", "payment", "status", "amount", "currency", "processed_at")
    list_filter = ("status", "currency", "created_at")
    search_fields = ("reference", "payment__reference", "payment__order__reference", "provider_reference")
    readonly_fields = [field.name for field in Refund._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(PaymentEvent)
class PaymentEventAdmin(admin.ModelAdmin):
    list_display = ("received_at", "provider", "event_type", "event_id", "signature_valid", "processed", "payment")
    list_filter = ("provider", "event_type", "signature_valid", "processed")
    search_fields = ("event_id", "payment__reference", "payment__order__reference", "payload_hash")
    readonly_fields = [field.name for field in PaymentEvent._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
