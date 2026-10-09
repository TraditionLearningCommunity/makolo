from __future__ import annotations

from django import forms
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.template.response import TemplateResponse

from operations.services import audit_action

from .credentials import set_provider_secret
from .health import test_provider_connection
from .models import IntelligenceRoute, ProviderConnection


class ProviderHealthCheckForm(forms.Form):
    reason = forms.CharField(min_length=5, max_length=2000, widget=forms.Textarea)


def _technical_superuser(request):
    user = request.user
    return bool(user.is_authenticated and user.is_active and user.is_staff and user.is_superuser)


class TechnicalConnectionAdminMixin:
    def has_module_permission(self, request):
        return _technical_superuser(request)

    def has_view_permission(self, request, obj=None):
        return _technical_superuser(request)

    def has_add_permission(self, request):
        return _technical_superuser(request)

    def has_change_permission(self, request, obj=None):
        return _technical_superuser(request)

    def has_delete_permission(self, request, obj=None):
        return False


class ProviderConnectionAdminForm(forms.ModelForm):
    api_key = forms.CharField(
        required=False,
        widget=forms.PasswordInput(render_value=False),
        help_text="Laisser vide pour conserver le credential existant. La clé n'est jamais réaffichée.",
    )

    class Meta:
        model = ProviderConnection
        fields = "__all__"


class IntelligenceRouteInline(admin.TabularInline):
    model = IntelligenceRoute
    extra = 0


@admin.register(ProviderConnection)
class ProviderConnectionAdmin(TechnicalConnectionAdminMixin, admin.ModelAdmin):
    form = ProviderConnectionAdminForm
    inlines = [IntelligenceRouteInline]
    list_display = ("name", "protocol", "scope", "enabled", "priority", "health_status", "last_checked_at")
    list_filter = ("protocol", "scope", "enabled", "health_status")
    search_fields = ("name", "base_url", "default_model")
    readonly_fields = ("health_status", "last_checked_at", "last_latency_ms", "credential_hint")
    actions = ("check_connections",)

    @admin.display(description="Credential")
    def credential_hint(self, obj):
        if not obj or not obj.pk:
            return "Non configuré"
        try:
            return obj.credential.key_hint or "Configuré"
        except Exception:
            return "Non configuré"

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        secret = form.cleaned_data.get("api_key", "").strip()
        if secret:
            set_provider_secret(connection=obj, secret=secret)

    @admin.action(description="Tester une connexion (justification obligatoire)")
    def check_connections(self, request, queryset):
        if not _technical_superuser(request):
            raise PermissionDenied("Maintenance Intelligence réservée aux administrateurs techniques.")
        selected = list(queryset.values_list("pk", flat=True)[:2])
        if len(selected) != 1:
            self.message_user(request, "Sélectionnez une seule connexion.", level=messages.ERROR)
            return
        connection = queryset.get(pk=selected[0])
        if request.POST.get("confirm_healthcheck") == "1":
            form = ProviderHealthCheckForm(request.POST)
            if form.is_valid():
                previous = connection.health_status
                status = test_provider_connection(connection)
                audit_action(
                    actor=request.user, action="intelligence.provider_checked",
                    target_type="provider_connection", target_id=connection.pk,
                    summary="Diagnostic technique explicite de connexion Intelligence",
                    before={"health_status": previous},
                    after={"health_status": status},
                    metadata={"reason": form.cleaned_data["reason"]},
                )
                self.message_user(request, "Contrôle enregistré et audité.", level=messages.SUCCESS)
                return
        else:
            form = ProviderHealthCheckForm()
        return TemplateResponse(
            request, "admin/intelligence/providerconnection/confirm_healthcheck.html",
            {
                **self.admin_site.each_context(request),
                "title": "Vérification technique d'une connexion",
                "opts": self.model._meta,
                "connection": connection,
                "form": form,
                "action": "check_connections",
                "action_checkbox_name": admin.helpers.ACTION_CHECKBOX_NAME,
            },
        )


@admin.register(IntelligenceRoute)
class IntelligenceRouteAdmin(TechnicalConnectionAdminMixin, admin.ModelAdmin):
    list_display = ("capability", "connection", "model", "priority", "enabled")
    list_filter = ("capability", "enabled", "connection__scope")
