"""Ephemeral Subscription -> action continuation, never an authority grant.

Only explicit owner-issued subscription denials produce a handoff. A safe
same-origin action URL allows a *new attempt*, never automatic replay or
unverified confirmation. No server session or extra persistent state.
"""
from urllib.parse import parse_qs, urlencode, urlsplit

from django.core.exceptions import ValidationError
from django.urls import Resolver404, resolve, reverse

from .authorization import subscriptions_visible_to_actor


def is_subscription_denial(error):
    return isinstance(error, ValidationError) and (
        "subscription" in getattr(error, "message_dict", {})
    )


def _action_return(request, *, space=None, action_url=None):
    if action_url is not None:
        return action_url
    if space is not None:
        return reverse("activities:create") + "?" + urlencode({"space": space.slug})
    return request.get_full_path()


def action_subscription_handoff(request, *, space=None, action_url=None):
    """Return a destination only if the viewer can read this exact Subscription."""
    if space is None:
        destination = reverse("subscriptions:home")
    else:
        authorized = subscriptions_visible_to_actor(request.user).filter(space=space).exists()
        if not authorized:
            return {
                "url": None,
                "message": (
                    "Cette capacité dépend de l’abonnement de l’Espace. "
                    "Une personne autorisée à consulter ou gérer son abonnement peut vérifier les conditions."
                ),
            }
        destination = reverse("organizations:console-subscription", args=[space.slug])
    continuation = _action_return(request, space=space, action_url=action_url)
    return {
        "url": destination + "?" + urlencode({"next": continuation}),
        "message": (
            "L’action est bloquée par une condition de l’abonnement. "
            "Consultez les capacités et conditions réelles, puis revenez tenter l’action."
        ),
    }


def safe_action_return(request, *, space=None):
    """Accept only local, explicit creation depths and exact Space contexts."""
    raw = request.POST.get("next", "") or request.GET.get("next", "")
    if not raw or len(raw) > 2048 or not raw.startswith("/") or raw.startswith("//"):
        return None
    if "\\" in raw or any(ord(char) < 32 for char in raw):
        return None
    parts = urlsplit(raw)
    if parts.scheme or parts.netloc or parts.fragment:
        return None
    try:
        match = resolve(parts.path)
    except Resolver404:
        return None
    name = match.view_name
    query = parse_qs(parts.query, keep_blank_values=True)
    if name in {"activities:create", "events:create"}:
        if set(query) - {"space"}:
            return None
    elif query:
        # Team creation has no query contract. Do not round-trip arbitrary data.
        return None
    # Event and Activity are both owner-scoped. A return link must not
    # silently reopen a personal creation after an Espace Subscription denial.
    if space is None:
        if name not in {"activities:create", "events:create"}:
            return None
        if "space" in query:
            return None
    else:
        if name in {"organizations:team-member-create", "organizations:member-create"}:
            if match.kwargs.get("slug") != space.slug:
                return None
        elif name in {"activities:create", "events:create"}:
            if query.get("space") != [space.slug]:
                return None
        else:
            return None
    return raw


def subscription_return_home(request, *, space=None):
    """Keep a validated continuation through server-side Subscription mutations."""
    if space is None:
        url = reverse("subscriptions:home")
    else:
        url = reverse("organizations:console-subscription", args=[space.slug])
    next_path = safe_action_return(request, space=space)
    return url + ("?" + urlencode({"next": next_path}) if next_path else "")
