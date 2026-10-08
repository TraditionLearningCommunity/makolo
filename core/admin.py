from django import forms
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.template.response import TemplateResponse

from domain_events.services import requeue_failed_domain_event

from .models import DomainEventConsumption, DomainEventOutbox, DomainEventStatus


class DomainEventRequeueForm(forms.Form):
    reason = forms.CharField(min_length=5, max_length=2000, widget=forms.Textarea)


@admin.register(DomainEventOutbox)
class DomainEventOutboxAdmin(admin.ModelAdmin):
    list_display = (
        "event_type", "source_type", "source_id", "status",
        "attempts", "max_attempts", "occurred_at", "processed_at",
    )
    list_filter = ("status", "event_type", "source_type")
    search_fields = ("id", "idempotency_key", "source_id")
    ordering = ("-created_at",)
    actions = ("requeue_failed_events",)

    def get_readonly_fields(self, request, obj=None):
        return tuple(field.name for field in self.model._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_actions(self, request):
        actions = super().get_actions(request)
        if not (request.user.is_active and request.user.is_staff and request.user.is_superuser):
            actions.pop("requeue_failed_events", None)
        return actions

    @admin.action(description="Reprise technique ciblée (raison obligatoire)")
    def requeue_failed_events(self, request, queryset):
        if not (request.user.is_active and request.user.is_staff and request.user.is_superuser):
            raise PermissionDenied
        ids = list(queryset.values_list("pk", flat=True)[:2])
        if len(ids) != 1:
            self.message_user(request, "Sélectionnez exactement un événement.", level=messages.ERROR)
            return
        event = queryset.get(pk=ids[0])
        if event.status != DomainEventStatus.FAILED:
            self.message_user(request, "Seul un événement échoué est éligible.", level=messages.ERROR)
            return
        if request.POST.get("confirm_requeue") == "1":
            form = DomainEventRequeueForm(request.POST)
            if form.is_valid():
                try:
                    requeue_failed_domain_event(
                        event_id=event.pk, actor=request.user,
                        reason=form.cleaned_data["reason"],
                    )
                except ValidationError as exc:
                    form.add_error(None, exc)
                else:
                    self.message_user(request, "Reprise enregistrée et auditée.", level=messages.SUCCESS)
                    return
        else:
            form = DomainEventRequeueForm()
        return TemplateResponse(
            request,
            "admin/core/domaineventoutbox/confirm_requeue.html",
            {
                **self.admin_site.each_context(request),
                "title": "Reprise exceptionnelle d'un Domain Event",
                "opts": self.model._meta,
                "event": event,
                "form": form,
                "action_checkbox_name": admin.helpers.ACTION_CHECKBOX_NAME,
                "action": "requeue_failed_events",
            },
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

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
