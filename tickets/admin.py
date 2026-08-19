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
    readonly_fields = ("ticket_type", "commerce_item", "quantity", "unit_price")


@admin.register(TicketType)
class TicketTypeAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "event",
        "offer",
        "capacity_pool",
        "display_price",
        "display_capacity",
        "display_available",
        "display_active",
    )
    list_filter = ("offer__status", "offer__currency", "capacity_pool__is_active", "event")
    search_fields = ("name", "slug", "event__activity__title", "offer__name")
    readonly_fields = (
        "slug",
        "offer",
        "capacity_pool",
        "canonical_price",
        "canonical_capacity",
        "canonical_availability",
        "created_at",
        "updated_at",
    )
    autocomplete_fields = ("event",)

    @admin.display(description="Tarif", ordering="offer__unit_price")
    def display_price(self, obj):
        return f"{obj.price} {obj.currency}"

    @admin.display(description="Capacité", ordering="capacity_pool__total_quantity")
    def display_capacity(self, obj):
        return obj.quantity_total if obj.quantity_total is not None else "Illimitée"

    @admin.display(description="Disponible")
    def display_available(self, obj):
        return obj.available_quantity if obj.available_quantity is not None else "Illimité"

    @admin.display(description="Actif", boolean=True)
    def display_active(self, obj):
        return obj.is_active

    def canonical_price(self, obj):
        return f"{obj.offer.unit_price} {obj.offer.currency}"

    canonical_price.short_description = "Offer — prix"

    def canonical_capacity(self, obj):
        return obj.capacity_pool.total_quantity

    canonical_capacity.short_description = "CapacityPool — total"

    def canonical_availability(self, obj):
        return obj.available_quantity

    canonical_availability.short_description = "CapacityPool — disponible"


@admin.register(TicketOrder)
class TicketOrderAdmin(admin.ModelAdmin):
    list_display = (
        "reference",
        "event",
        "customer_email",
        "display_status",
        "display_total",
        "created_at",
    )
    list_filter = ("commerce_order__status", "commerce_order__currency", "event")
    search_fields = ("reference", "customer_name", "customer_email", "event__activity__title")
    readonly_fields = (
        "reference",
        "journey",
        "commerce_order",
        "canonical_status_display",
        "canonical_total_display",
        "confirmed_at",
        "cancelled_at",
        "created_at",
        "updated_at",
    )
    autocomplete_fields = ("event", "buyer")
    inlines = (TicketOrderItemInline,)

    @admin.display(description="Statut")
    def display_status(self, obj):
        return obj.canonical_status

    @admin.display(description="Total")
    def display_total(self, obj):
        return f"{obj.canonical_total} {obj.canonical_currency}"

    def canonical_status_display(self, obj):
        return obj.canonical_status

    canonical_status_display.short_description = "CommerceOrder — statut"

    def canonical_total_display(self, obj):
        return f"{obj.canonical_total} {obj.canonical_currency}"

    canonical_total_display.short_description = "CommerceOrder — valeur"


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "event",
        "ticket_type",
        "holder_email",
        "display_status",
        "access",
        "issued_at",
    )
    list_filter = ("access__status", "event", "ticket_type")
    search_fields = ("code", "holder_name", "holder_email", "order__reference", "event__activity__title")
    readonly_fields = (
        "code",
        "event",
        "ticket_type",
        "order",
        "access",
        "owner",
        "holder_name",
        "holder_email",
        "canonical_status_display",
        "issued_at",
        "used_at",
        "cancelled_at",
        "created_at",
        "updated_at",
    )

    @admin.display(description="Statut")
    def display_status(self, obj):
        return obj.display_status

    def canonical_status_display(self, obj):
        return obj.display_status

    canonical_status_display.short_description = "Access — statut Event"


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
        "ticket_type__event__activity__title",
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
        "ticket__event__activity__title",
        "sender__email",
        "recipient__email",
        "recipient_email",
    )
    readonly_fields = [field.name for field in TicketTransfer._meta.fields]

    def has_add_permission(self, request):
        return False
