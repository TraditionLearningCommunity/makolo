from django.contrib import admin

from .models import Ticket, TicketOrder, TicketOrderItem, TicketType


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
