from __future__ import annotations

from django import forms
from django.contrib import admin

from .credentials import set_provider_secret
from .health import test_provider_connection
from .models import IntelligenceRoute, ProviderConnection


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
class ProviderConnectionAdmin(admin.ModelAdmin):
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

    @admin.action(description="Tester les connexions sélectionnées")
    def check_connections(self, request, queryset):
        for connection in queryset:
            test_provider_connection(connection)


@admin.register(IntelligenceRoute)
class IntelligenceRouteAdmin(admin.ModelAdmin):
    list_display = ("capability", "connection", "model", "priority", "enabled")
    list_filter = ("capability", "enabled", "connection__scope")
