"""Small Web forms for owner-controlled Intelligence connections.

Views authenticate and check scope authority before calling these helpers.
"""
from __future__ import annotations

from uuid import UUID
from urllib.parse import urlencode

from django.contrib import messages
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.http import Http404
from django.shortcuts import redirect

from intelligence.connection_management import (
    catalog, create_connection, disconnect_connection, update_connection,
)
from intelligence.models import ProviderConnection, ProviderScope


def connection_form_context():
    offers = catalog()
    return {
        "connection_offers": offers,
        "connection_can_connect": any(offer["can_connect"] for offer in offers),
    }


def _connections_return_url(request):
    """Return only to this owner surface; never redirect to a client URL."""
    params = {"tab": "mine"}
    responsibility = request.GET.get("responsibility", "").strip()[:80]
    if responsibility:
        params["responsibility"] = responsibility
    return f"{request.path}?{urlencode(params)}"


def handle_connection_form(request, *, scope, space=None):
    """No secret or internal provider endpoint is included in a response/message."""
    action = request.POST.get("operation", "")
    if action not in {"create", "disable", "enable", "disconnect", "rotate"}:
        raise Http404()
    owner = {"scope": scope}
    if scope == ProviderScope.PROFILE:
        owner["profile__user"] = request.user
    elif scope == ProviderScope.SPACE:
        if space is None:
            raise Http404()
        owner["space"] = space
    elif scope != ProviderScope.PLATFORM:
        raise Http404()

    if action == "create":
        try:
            create_connection(
                actor=request.user,
                scope=scope,
                space=space,
                payload={
                    "provider": request.POST.get("provider", ""),
                    "name": request.POST.get("name", ""),
                    "model": request.POST.get("model", ""),
                    "api_key": request.POST.get("api_key", ""),
                    "consent": request.POST.get("consent") == "yes",
                },
            )
            messages.success(request, "Connexion enregistrée. Sa disponibilité sera vérifiée lors de son utilisation.")
        except (ValidationError, ImproperlyConfigured, ValueError):
            messages.error(request, "Connexion non créée : vérifiez le fournisseur, le modèle, la clé et la configuration.")
        return redirect(_connections_return_url(request))

    try:
        connection_id = UUID(request.POST.get("connection_id", ""))
    except (TypeError, ValueError):
        raise Http404() from None

    connection = ProviderConnection.objects.filter(**owner, pk=connection_id).first()
    if connection is None:
        raise Http404()

    if action == "disconnect":
        if request.POST.get("confirm") != "yes":
            messages.error(request, "Confirmez le retrait avant de poursuivre.")
        else:
            disconnect_connection(actor=request.user, connection=connection)
            messages.success(request, "Connexion retirée de Makolo. Révoquez séparément la clé chez le fournisseur si nécessaire.")
        return redirect(_connections_return_url(request))

    update = {"enabled": action == "enable"} if action in {"enable", "disable"} else {
        "api_key": request.POST.get("api_key", ""),
    }
    try:
        update_connection(actor=request.user, connection=connection, payload=update)
        messages.success(request, "Connexion mise à jour.")
    except (ValidationError, ImproperlyConfigured, ValueError):
        messages.error(request, "Modification impossible ; vérifiez les informations et la configuration.")
    return redirect(_connections_return_url(request))
