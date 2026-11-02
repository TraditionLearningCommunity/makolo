"""Connexion demo: audit du catalogue et des relations REELLEMENT autorisees.

Aucun provider fictivement connecte, credential, token Push ou OAuth fabrique.
Le catalogue est deja code (OFFERS). Les connexions actives necessitent le
consentement explicite du proprietaire et une cle fournie par le provider.
"""
import argparse
from collections import Counter


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    import django
    django.setup()
    from django.db import connection
    from intelligence.connection_management import catalog
    from intelligence.models import (
        ProviderConnection, ProviderCredential, IntelligenceRoute, ProviderScope,
    )
    from notifications.models import PushEndpoint

    if connection.vendor != "sqlite":
        parser.error("Demo coverage is limited to SQLite")
    counts = Counter()
    offers = catalog()
    counts["connectable_offers"] = len(offers)
    counts["offers_currently_connectable"] = sum(bool(row["can_connect"]) for row in offers)
    for scope in ProviderScope.values:
        counts["connections_" + scope] = ProviderConnection.objects.filter(scope=scope).count()
    counts["provider_connections"] = ProviderConnection.objects.count()
    counts["encrypted_credentials"] = ProviderCredential.objects.count()
    counts["intelligence_routes"] = IntelligenceRoute.objects.count()
    counts["push_endpoints"] = PushEndpoint.objects.count()
    counts["disabled_without_credential"] = ProviderConnection.objects.filter(
        enabled=False, credential__isnull=True).count()
    counts["enabled_without_credential"] = ProviderConnection.objects.filter(
        enabled=True, credential__isnull=True).count()
    print("CONNECTIONS", "APPLY" if args.apply else "PREVIEW", dict(sorted(counts.items())))
    print("PROVIDERS", [(row["code"], row["requires_model"], row["can_connect"]) for row in offers])
    print("No synthetic credentials, consent, successful health or device registrations.")
    if args.apply:
        print("No mutations: owner-controlled Connections are created through their authorized API only.")
    if counts["enabled_without_credential"]:
        print("WARNING: enabled provider connections without a stored credential; inspect via owner services.")


if __name__ == "__main__":
    main()
