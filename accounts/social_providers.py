from dataclasses import dataclass

from allauth.socialaccount.models import SocialApp


@dataclass(frozen=True)
class SocialProviderSpec:
    id: str
    name: str
    provider: str
    callback_path: str
    provider_id: str = ""
    required_server_url: str = ""


SOCIAL_PROVIDER_SPECS = (
    SocialProviderSpec(
        id="google",
        name="Google",
        provider="google",
        callback_path="/auth/google/login/callback/",
    ),
    SocialProviderSpec(
        id="facebook",
        name="Facebook",
        provider="facebook",
        callback_path="/auth/facebook/login/callback/",
    ),
    SocialProviderSpec(
        id="microsoft",
        name="Microsoft",
        provider="microsoft",
        callback_path="/auth/microsoft/login/callback/",
    ),
    SocialProviderSpec(
        id="linkedin",
        name="LinkedIn",
        provider="openid_connect",
        provider_id="linkedin",
        callback_path="/auth/oidc/linkedin/login/callback/",
        required_server_url="https://www.linkedin.com/oauth",
    ),
)


def _app_matches(app: SocialApp, spec: SocialProviderSpec) -> bool:
    if app.provider != spec.provider:
        return False
    if spec.provider_id and getattr(app, "provider_id", "") != spec.provider_id:
        return False
    if not (app.client_id or "").strip() or not (app.secret or "").strip():
        return False

    if spec.required_server_url:
        settings = getattr(app, "settings", {}) or {}
        server_url = (settings.get("server_url") or "").rstrip("/")
        if server_url != spec.required_server_url.rstrip("/"):
            return False

    return True


def social_provider_statuses() -> list[dict[str, object]]:
    apps = list(SocialApp.objects.all())
    return [
        {
            "id": spec.id,
            "name": spec.name,
            "configured": any(_app_matches(app, spec) for app in apps),
        }
        for spec in SOCIAL_PROVIDER_SPECS
    ]
