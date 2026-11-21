"""Seed 50 explicitly simulated connection options across existing beta users.

Never creates a provider secret or marks a simulation externally usable.
"""
import argparse
from collections import Counter


def offer_index(slot, profile_count, offer_count):
    """Rotate every choice through every Profile before advancing to the next."""
    if profile_count < 1 or offer_count < 1:
        raise ValueError("Au moins un Profil et une offre sont requis.")
    return (slot // profile_count) % offer_count


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--count", type=int, default=50)
    parser.add_argument("--profiles", type=int, default=2)
    parser.add_argument("--profile-username", default=None)
    a = parser.parse_args(argv)
    if not 1 <= a.count <= 5000 or not 1 <= a.profiles <= 100:
        parser.error("count 1..5000 / profiles 1..100")
    import django
    django.setup()
    from django.contrib.auth import get_user_model
    from django.db import connection
    from django.db.models import Q
    from intelligence.connection_management import catalog
    from intelligence.demo_connections import demo_offers, create_demo_connection
    from intelligence.models import ProviderConnection, ProviderCredential, IntelligenceRoute, ProviderScope
    from accounts.models import UserProfile
    from notifications.models import PushEndpoint

    if connection.vendor != "sqlite":
        parser.error("SQLite de demonstration uniquement")
    people = get_user_model().objects.filter(is_active=True, is_staff=False, is_superuser=False)
    if a.profile_username:
        people = people.filter(username=a.profile_username)
    else:
        people = people.filter(username__startswith="world_")
    people = list(people.order_by("username")[:a.profiles])
    offers = demo_offers()
    counts = Counter()
    counts["catalog_real"] = len(catalog())
    counts["catalog_demo"] = len(offers)
    counts["users_selected"] = len(people)
    counts["push_endpoints_existing"] = PushEndpoint.objects.count()
    counts["provider_connections_existing"] = ProviderConnection.objects.count()
    counts["credentials_existing"] = ProviderCredential.objects.count()
    counts["routes_existing"] = IntelligenceRoute.objects.count()
    if not people:
        print("CONNECTIONS", "APPLY" if a.apply else "PREVIEW", dict(counts))
        print("Aucun utilisateur de demonstration admissible. Aucun compte cree.")
        return
    # Give every existing selected user a distinct subset, with all 50 offers
    # represented whenever count>=50. No arbitrary fake provider brands.
    for index in range(min(a.count, len(offers) * len(people))):
        actor = people[index % len(people)]
        # Every selected profile receives successive choices, not just even/odd subsets.
        offer = offers[offer_index(index, len(people), len(offers))]
        profile = UserProfile.objects.filter(user=actor).first()
        exists = bool(profile and ProviderConnection.objects.filter(
            scope=ProviderScope.PROFILE, profile=profile,
        ).filter(Q(name=offer["label"], default_model="demo-disabled") |
                 Q(name="[DEMO Connexion] " + offer["label"])).exists())
        if exists:
            counts["already_connected_demo"] += 1
        elif not a.apply:
            counts["demo_connections_planned"] += 1
        else:
            obj, created = create_demo_connection(
                actor=actor, scope=ProviderScope.PROFILE,
                provider=offer["code"], consent=True,
            )
            counts["demo_connections_created" if created else "already_connected_demo"] += 1
    print("CONNECTIONS", "APPLY" if a.apply else "PREVIEW", dict(sorted(counts.items())))
    print("Simulations locales desactivees: aucun credential, token Push ou appel provider.")


if __name__ == "__main__":
    main()
