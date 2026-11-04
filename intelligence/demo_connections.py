"""Fixed simulated connection choices for beta UX.

Demo connections use canonical ProviderConnection and IntelligenceRoute storage,
but are ALWAYS disabled and NEVER have credentials. No gateway may dispatch them.
"""
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from accounts.models import UserProfile
from .capabilities import IntelligenceCapability
from .models import ProviderConnection, ProviderHealth, ProviderProtocol, ProviderScope, IntelligenceRoute

CATEGORIES = (
    ("recherche", "Recherche", IntelligenceCapability.WEB_RESEARCH.value, ProviderProtocol.TAVILY_SEARCH, "https://api.tavily.com"),
    ("sources", "Sources", IntelligenceCapability.WEB_RESEARCH.value, ProviderProtocol.EXA_SEARCH, "https://api.exa.ai"),
    ("redaction", "Rédaction", IntelligenceCapability.TEXT_GENERATE.value, ProviderProtocol.OPENAI_COMPATIBLE, "https://api.openai.com/v1"),
    ("analyse", "Analyse structurée", IntelligenceCapability.STRUCTURED_GENERATE.value, ProviderProtocol.OPENAI_COMPATIBLE, "https://api.openai.com/v1"),
    ("semantique", "Recherche sémantique", IntelligenceCapability.EMBED.value, ProviderProtocol.OPENAI_COMPATIBLE, "https://api.openai.com/v1"),
)
CONTEXTS = ("Études", "Voyages", "Emploi", "Entrepreneuriat", "Événements", "Démarches", "Santé", "Formation", "Culture", "Commerce")
PREFIX = ""


def demo_offers():
    return [
        {
            "code": "demo-" + code + "-" + str(index + 1).zfill(2),
            "label": PREFIX + label + " — " + context,
            "description": label + " appliquée au domaine " + context.lower() + ".",
            "capabilities": [capability],
            "requires_model": False,
            "can_connect": True,
            "demo": True,
            "category": code,
        }
        for code, label, capability, _protocol, _url in CATEGORIES
        for index, context in enumerate(CONTEXTS)
    ]


@transaction.atomic
def create_demo_connection(*, actor, scope, provider, consent, space=None):
    if consent is not True:
        raise ValidationError({"consent": "Consentement explicite nécessaire."})
    offer = next((item for item in demo_offers() if item["code"] == provider), None)
    if offer is None:
        raise ValidationError({"provider": "Simulation inconnue."})
    category = next(row for row in CATEGORIES if row[0] == offer["category"])
    from .connection_management import _assert_management
    if scope == ProviderScope.PROFILE:
        profile, _ = UserProfile.objects.get_or_create(user=actor)
        _assert_management(actor=actor, scope=scope, profile=profile)
        owner = {"profile": profile, "space": None}
    elif scope == ProviderScope.SPACE:
        _assert_management(actor=actor, scope=scope, space=space)
        owner = {"profile": None, "space": space}
    else:
        _assert_management(actor=actor, scope=scope)
        owner = {"profile": None, "space": None}
    name = offer["label"]
    legacy = ProviderConnection.objects.filter(scope=scope, **owner).filter(
        Q(name="[DEMO Connexion] " + name) |
        Q(name=name, default_model="demo-disabled")
    ).first()
    if legacy:
        if legacy.name != name or legacy.default_model != "demo-disabled" or legacy.enabled:
            legacy.name = name
            legacy.default_model = "demo-disabled"
            legacy.enabled = False
            legacy.save(update_fields=["name", "default_model", "enabled", "updated_at"])
        return legacy, False
    obj, created = ProviderConnection.objects.get_or_create(
        scope=scope, name=name, default_model="demo-disabled", **owner,
        defaults={
            "protocol": category[3],
            "base_url": category[4],
            "enabled": False,
            "health_status": ProviderHealth.UNKNOWN,
        },
    )
    if created:
        IntelligenceRoute.objects.create(
            connection=obj, capability=category[2], enabled=False)
    return obj, created
