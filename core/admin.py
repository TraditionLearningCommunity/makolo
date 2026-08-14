from django.contrib import admin
from django.utils import timezone

from .models import DomainEventConsumption, DomainEventOutbox, DomainEventStatus


@admin.register(DomainEventOutbox)
class DomainEventOutboxAdmin(admin.ModelAdmin):
    list_display = (
        "event_type",
        "source_type",
        "source_id",
        "status",
        "attempts",
        "occurred_at",
        "processed_at",
    )
    list_filter = ("status", "event_type", "source_type")
    search_fields = ("id", "idempotency_key", "source_id")
    ordering = ("-created_at",)
    actions = ("requeue_failed_events",)

    def get_readonly_fields(self, request, obj=None):
        return tuple(field.name for field in self.model._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.action(description="Remettre les Domain Events échoués en attente")
    def requeue_failed_events(self, request, queryset):
        now = timezone.now()
        queryset.filter(status=DomainEventStatus.FAILED).update(
            status=DomainEventStatus.PENDING,
            claimed_at=None,
            processed_at=None,
            last_error="",
            attempts=0,
            updated_at=now,
        )


@admin.register(DomainEventConsumption)
class DomainEventConsumptionAdmin(admin.ModelAdmin):
    list_display = ("event", "consumer", "status", "attempts", "processed_at")
    list_filter = ("status", "consumer")
    search_fields = ("event__id", "event__event_type", "consumer")
    ordering = ("-created_at",)

    def get_readonly_fields(self, request, obj=None):
        return tuple(field.name for field in self.model._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
