from django.contrib import admin

from .models import Notification, NotificationDelivery


class NotificationDeliveryInline(admin.TabularInline):
    model = NotificationDelivery
    extra = 0
    can_delete = False
    readonly_fields = (
        "channel",
        "destination",
        "status",
        "scheduled_for",
        "attempts",
        "max_attempts",
        "provider_reference",
        "last_error",
        "skipped_reason",
        "sent_at",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("title", "recipient", "category", "kind", "read_at", "created_at")
    list_filter = ("category", "kind", "read_at", "created_at")
    search_fields = ("title", "message", "recipient__email", "recipient__username", "dedup_key")
    readonly_fields = (
        "recipient",
        "kind",
        "category",
        "title",
        "message",
        "action_url",
        "dedup_key",
        "metadata",
        "read_at",
        "created_at",
        "updated_at",
    )
    inlines = [NotificationDeliveryInline]

    def has_add_permission(self, request):
        return False


@admin.register(NotificationDelivery)
class NotificationDeliveryAdmin(admin.ModelAdmin):
    list_display = ("notification", "channel", "destination", "status", "attempts", "scheduled_for", "sent_at")
    list_filter = ("channel", "status", "scheduled_for", "sent_at")
    search_fields = ("notification__title", "destination", "provider_reference")
    readonly_fields = [field.name for field in NotificationDelivery._meta.fields]

    def has_add_permission(self, request):
        return False
