"""Django model coverage: inventory every installed model and its demo provenance.

This is a policy audit, not a generic ORM factory: a model's row count cannot
prove that its domain contract or permission checks have been exercised.
"""
import argparse
from collections import Counter

INFRASTRUCTURE_APPS = frozenset({
    "admin", "auth", "contenttypes", "sessions", "token_blacklist",
    "account", "socialaccount",
})
RUNTIME_APPS = frozenset({
    "observer_storage", "interpreter_storage", "prospector_storage",
    "resolver_storage", "intelligence",
})
DOMAIN_GENERATORS = {
    "activities": "activities/transport/foundations",
    "authorization": "mandates",
    "journeys": "journeys/foundations/community",
    "access": "access/scanner",
    "operations": "operations/placement/incidents",
    "scanner": "scanner",
    "events": "commerce/scanner",
    "tickets": "commerce/scanner",
    "commerce": "commerce",
    "payments": "commerce/funding [sandbox only]",
    "capacity": "transport/commerce",
    "transport": "transport",
    "funding": "funding",
    "services": "services",
    "obtention": "obtention",
    "opportunities": "opportunities",
    "presentations": "media/content",
    "preparation": "content [existing facts]",
    "groups": "groups",
    "objectives": "objectives",
    "trust": "trust [eligible feedback only]",
    "notifications": "notifications [in-app only]",
    "crm": "crm [derive from sales]",
    "questionnaires": "forms",
    "social": "contributions",
}
DERIVED_APPS = frozenset({
    "analytics_app", "recognition", "growth", "loyalty",
    "automation", "subscriptions",
})
DEPENDENCY_APPS = frozenset({
    "organizations", "geography", "topics", "accounts",
    "conversations", "sharing", "personal_assets",
    "requirements", "promotions", "partners",
})


def policy_for(model):
    """A deterministic classification for *each* installed Django model."""
    label = model._meta.label
    app = model._meta.app_label
    name = model.__name__.lower()
    if name in {"providercredential", "socialtoken", "accesscredential",
                "credential", "pushendpoint", "userdevice", "usersession"}:
        return "protected", "Secret or user/device credential: use owner service only"
    if app in INFRASTRUCTURE_APPS:
        return "runtime", "Django or dependency framework"
    if app in RUNTIME_APPS:
        return "observed", "Process/engine evidence, not made-up observations"
    if app in DERIVED_APPS:
        return "derived", "Must follow actions and domain events"
    if app in DOMAIN_GENERATORS:
        return "domain", DOMAIN_GENERATORS[app]
    if app in DEPENDENCY_APPS:
        return "context", "Requires an explicit owner/context and scenario contract"
    return "review", "Unclassified app: inspect domain contract before seeding"


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--empty-only", action="store_true")
    p.add_argument("--app", help="Limit displayed records to one Django app label")
    a = p.parse_args(argv)
    import django
    django.setup()
    from django.apps import apps
    from django.db import connection, DatabaseError
    if connection.vendor != "sqlite":
        p.error("Demo model coverage inventory requires SQLite")
    counters = Counter()
    by_policy = Counter()
    models = sorted(apps.get_models(), key=lambda m: m._meta.label_lower)
    counters["total"] = len(models)
    for model in models:
        try:
            count = model.objects.count()
        except DatabaseError:
            counters["unavailable"] += 1
            print("MODEL",model._meta.label, "UNAVAILABLE", "schema_not_accessible")
            continue
        policy, reason = policy_for(model)
        counters["populated" if count else "empty"] += 1
        by_policy[(policy, "populated" if count else "empty")] += 1
        if a.app and model._meta.app_label != a.app:
            continue
        if a.empty_only and count:
            continue
        print("MODEL", model._meta.label, count, policy,
              "domain=" + reason.replace(" ", "_"))
    print("MODELS_TOTAL", counters["total"],
          "POPULATED", counters["populated"], "EMPTY", counters["empty"],
          "UNAVAILABLE", counters["unavailable"])
    for (category, state), count in sorted(by_policy.items()):
        print("POLICY", category, state, count)
    print("Model inventory covers the installed registry, not a promise of 338 "
          "fabricated rows. Empty runtime/secret/provider models may be correct.")


if __name__ == "__main__":
    main()
