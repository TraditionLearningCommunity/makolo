from django.contrib import admin

from .models import EventFeedback, MarketingAttribution, MarketingLink, MarketingLinkVisit


@admin.register(MarketingLink)
class MarketingLinkAdmin(admin.ModelAdmin):
    list_display = ("name", "organization", "event", "channel", "code", "is_active", "created_at")
    list_filter = ("channel", "is_active", "created_at")
    search_fields = ("name", "code", "organization__name", "event__title")
    raw_id_fields = ("organization", "event", "crm_campaign", "created_by")
    readonly_fields = ("code", "created_at", "updated_at")


@admin.register(MarketingLinkVisit)
class MarketingLinkVisitAdmin(admin.ModelAdmin):
    list_display = ("link", "user", "referrer_domain", "visited_at")
    list_filter = ("visited_at",)
    search_fields = ("link__code", "link__name", "referrer_domain")
    raw_id_fields = ("link", "user")
    readonly_fields = ("link", "user", "session_key_hash", "referrer_domain", "visited_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(MarketingAttribution)
class MarketingAttributionAdmin(admin.ModelAdmin):
    list_display = ("order", "link", "status", "revenue_amount", "currency", "attributed_at")
    list_filter = ("status", "currency", "attributed_at")
    search_fields = ("order__reference", "link__code", "link__name")
    raw_id_fields = ("order", "link", "visit")
    readonly_fields = (
        "order", "link", "visit", "status", "revenue_amount", "currency",
        "attributed_at", "confirmed_at", "reversed_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(EventFeedback)
class EventFeedbackAdmin(admin.ModelAdmin):
    list_display = ("event", "user", "rating", "created_at")
    list_filter = ("rating", "created_at")
    search_fields = ("event__title", "user__email", "comment")
    raw_id_fields = ("event", "user")
    readonly_fields = ("created_at", "updated_at")
