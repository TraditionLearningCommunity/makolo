from django.contrib import admin

from .models import (
    Ticket,
    TicketOrder,
    TicketOrderItem,
    TicketTransfer,
    TicketType,
    TicketWaitlistEntry,
)


class TicketOrderItemInline(admin.TabularInline):
    model = TicketOrderItem
    extra = 0
    readonly_fields = ("ticket_type", "quantity", "unit_price")


@admin.register(TicketType)
class TicketTypeAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "event",
        "price",
        "currency",
        "quantity_total",
        "reserved_quantity",
        "issued_quantity",
        "is_active",
    )
    list_filter = ("is_active", "currency", "event")
    search_fields = ("name", "slug", "event__title")
    readonly_fields = ("slug", "reserved_quantity", "issued_quantity", "created_at", "updated_at")
    autocomplete_fields = ("event",)


@admin.register(TicketOrder)
class TicketOrderAdmin(admin.ModelAdmin):
    list_display = (
        "reference",
        "event",
        "customer_email",
        "status",
        "total_amount",
        "currency",
        "created_at",
    )
    list_filter = ("status", "currency", "event")
    search_fields = ("reference", "customer_name", "customer_email", "event__title")
    readonly_fields = (
        "reference",
        "total_amount",
        "confirmed_at",
        "cancelled_at",
        "created_at",
        "updated_at",
    )
    autocomplete_fields = ("event", "buyer")
    inlines = (TicketOrderItemInline,)


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "event",
        "ticket_type",
        "holder_email",
        "status",
        "issued_at",
    )
    list_filter = ("status", "event", "ticket_type")
    search_fields = ("code", "holder_name", "holder_email", "order__reference")
    readonly_fields = (
        "code",
        "event",
        "ticket_type",
        "order",
        "owner",
        "holder_name",
        "holder_email",
        "issued_at",
        "created_at",
        "updated_at",
    )


@admin.register(TicketWaitlistEntry)
class TicketWaitlistEntryAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "ticket_type",
        "requested_quantity",
        "status",
        "offered_at",
        "offer_expires_at",
        "created_at",
    )
    list_filter = ("status", "ticket_type__event")
    search_fields = (
        "user__email",
        "user__username",
        "ticket_type__name",
        "ticket_type__event__title",
        "offered_order__reference",
    )
    readonly_fields = (
        "ticket_type",
        "user",
        "requested_quantity",
        "status",
        "offered_order",
        "offered_at",
        "offer_expires_at",
        "converted_at",
        "cancelled_at",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request):
        return False


@admin.register(TicketTransfer)
class TicketTransferAdmin(admin.ModelAdmin):
    list_display = (
        "ticket",
        "sender",
        "recipient",
        "status",
        "expires_at",
        "accepted_at",
        "created_at",
    )
    list_filter = ("status", "ticket__event")
    search_fields = (
        "ticket__code",
        "ticket__event__title",
        "sender__email",
        "recipient__email",
        "recipient_email",
    )
    readonly_fields = [field.name for field in TicketTransfer._meta.fields]

    def has_add_permission(self, request):
        return False
