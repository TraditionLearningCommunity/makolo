"""Guard framework OAuth configuration and credential inspection.

allauth remains the OAuth/OIDC owner; this overrides only its technical Admin
forms, not provider handshake, account linkage or persistent schema.
"""
from django import forms
from django.contrib import admin

from allauth.socialaccount.admin import SocialAccountAdmin, SocialAppAdmin, SocialAppForm, SocialTokenAdmin
from allauth.socialaccount.models import SocialAccount, SocialApp, SocialToken

from .admin_boundaries import TechnicalSuperuserReadOnlyAdmin


def _technical_superuser(request):
    user = request.user
    return bool(user.is_authenticated and user.is_active and user.is_staff and user.is_superuser)


class SecretSafeSocialAppForm(SocialAppForm):
    """Never prepopulate credentials or opaque provider settings from DB."""

    new_secret = forms.CharField(
        required=False,
        widget=forms.PasswordInput(render_value=False),
        label="Nouveau secret (facultatif)",
        help_text="Laisser vide pour conserver le secret déjà configuré.",
    )
    new_key = forms.CharField(
        required=False,
        widget=forms.PasswordInput(render_value=False),
        label="Nouvelle clé (facultative)",
        help_text="Laisser vide pour conserver la clé déjà configurée.",
    )
    settings_payload = forms.JSONField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 4}),
        label="Remplacement intégral des paramètres (facultatif)",
        help_text="Ne jamais afficher les paramètres actuels. Laisser vide pour les conserver.",
    )

    class Meta(SocialAppForm.Meta):
        exclude = ("secret", "key", "settings")


class TechnicalSocialAppAdmin(SocialAppAdmin):
    form = SecretSafeSocialAppForm
    list_display = ("name", "provider")

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

    def save_model(self, request, obj, form, change):
        # A blank replacement retains encrypted-at-rest/out-of-band values; do
        # not accidentally overwrite an existing provider secret with blanks.
        secret = form.cleaned_data.get("new_secret")
        key = form.cleaned_data.get("new_key")
        settings = form.cleaned_data.get("settings_payload")
        if secret:
            obj.secret = secret
        if key:
            obj.key = key
        if settings is not None:
            obj.settings = settings
        super().save_model(request, obj, form, change)


class TechnicalSocialTokenAdmin(TechnicalSuperuserReadOnlyAdmin, SocialTokenAdmin):
    # The upstream truncated_token leaks the first characters of a live token.
    list_display = ("app", "account", "token_present", "expires_at")

    @admin.display(boolean=True, description="Token configuré")
    def token_present(self, obj):
        return bool(obj.token)

    def get_fields(self, request, obj=None):
        return tuple(
            name for name in super().get_fields(request, obj)
            if name not in {"token", "token_secret"}
        )


class TechnicalSocialAccountAdmin(TechnicalSuperuserReadOnlyAdmin, SocialAccountAdmin):
    """OAuth identity linkage must not be reassigned as arbitrary Admin CRUD."""


# allauth.socialaccount precedes core in INSTALLED_APPS; its standard Admin
# registrations are already present when this module is imported by core.admin.
for _model, _admin_class in (
    (SocialApp, TechnicalSocialAppAdmin),
    (SocialToken, TechnicalSocialTokenAdmin),
    (SocialAccount, TechnicalSocialAccountAdmin),
):
    if _model in admin.site._registry:
        admin.site.unregister(_model)
    admin.site.register(_model, _admin_class)
