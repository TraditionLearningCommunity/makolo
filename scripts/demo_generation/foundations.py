"""Créer des Activity synthétiques pour Funding, Services et Obtention.

Une seule Activity canonique possède sa spécialisation métier. Ce module ne
duplique ni Payment, ni Proof, ni les données des Activities existantes.
"""
import argparse
from collections import Counter
from datetime import timedelta


DOMAINS = ("funding", "services", "obtention")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--domains", default=",".join(DOMAINS))
    p.add_argument("--count", type=int, default=4)
    p.add_argument("--apply", action="store_true")
    a = p.parse_args(argv)
    selected = set(a.domains.split(","))
    if not selected or not selected <= set(DOMAINS) or not 1 <= a.count <= 100:
        p.error("Domaines: funding,services,obtention; count 1..100")
    import django
    django.setup()
    from django.contrib.auth import get_user_model
    from django.core.exceptions import PermissionDenied, ValidationError
    from django.db import connection, transaction
    from django.utils import timezone
    from activities.models import Activity, ActivityStatus
    from activities.services import create_activity
    from funding.models import FundingDetails
    from funding.services import create_funding
    from services.models import ServiceDetails, ServiceKind
    from authorization.constants import SystemRoleCode
    from authorization.services import grant_activity_role
    from services.services import create_service_details
    from obtention.models import ObtentionDetails, ObtentionModeCode
    from obtention.services import create_obtention
    if connection.vendor != "sqlite":
        p.error("La génération est limitée à une base SQLite de démonstration")
    people = list(get_user_model().objects.filter(
        username__startswith="world_", is_active=True,
        is_staff=False, is_superuser=False,
    ).order_by("username")[:min(a.count, 100)])
    if not people:
        p.error("Aucun profil world_* de démonstration admissible")
    now = timezone.now()
    counters = Counter()
    labels = {
        "funding": "Soutien éducatif local",
        "services": "Accompagnement aux démarches",
        "obtention": "Obtention de fournitures scolaires",
    }
    for domain in DOMAINS:
        if domain not in selected:
            continue
        for index in range(a.count):
            owner = people[index % len(people)]
            suffix = f"{index + 1:04d}"
            slug = f"demo-generation-{domain}-{suffix}"
            title = f"[DEMO] {labels[domain]} {suffix}"
            activity = Activity.objects.filter(owner_profile=owner, slug=slug).first()
            if activity:
                detail_present = {
                    "funding": FundingDetails.objects.filter(activity=activity).exists(),
                    "services": ServiceDetails.objects.filter(activity=activity).exists(),
                    "obtention": ObtentionDetails.objects.filter(activity=activity).exists(),
                }[domain]
                counters[domain + ("_existing" if detail_present else "_incomplete")] += 1
                continue
            if not a.apply:
                counters[domain + "_planned"] += 1
                continue
            try:
                with transaction.atomic():
                    if domain == "funding":
                        detail = create_funding(
                            actor=owner, title=title,
                            short_description="Collecte fictive pour tester Funding.",
                            description="Simulation locale, aucun financement réel.",
                            target_amount="5000.00", currency="USD",
                            minimum_contribution="1.00",
                            maximum_contribution="1000.00",
                            opens_at=now - timedelta(days=1),
                            closes_at=now + timedelta(days=90),
                            status=ActivityStatus.PUBLISHED,
                        )
                        activity = detail.activity
                    elif domain == "services":
                        activity = create_activity(
                            created_by=owner, owner_profile=owner, title=title,
                            status=ActivityStatus.PUBLISHED,
                            short_description="Service fictif de préparation administrative.",
                        )
                        grant_activity_role(
                            profile=owner, activity=activity,
                            role=SystemRoleCode.ACTIVITY_SERVICE_MANAGER,
                            granted_by=owner, source="demo-generation-services",
                        )
                        create_service_details(
                            activity=activity, actor=owner,
                            service_kind=ServiceKind.ADMINISTRATIVE_SUPPORT,
                        )
                    else:
                        detail = create_obtention(
                            actor=owner, title=title,
                            targets=[{"title": "Kit scolaire", "quantity": 1,
                                      "unit": "kit"}],
                            modes=[ObtentionModeCode.RECEIVE],
                            result_label="Kit scolaire remis",
                            short_description="Attribution fictive à préparer.",
                            status=ActivityStatus.PUBLISHED,
                        )
                        activity = detail.activity
                    # Create services own Activity; mark synthetic provenance through
                    # its immutable scenario slug without changing ownership.
                    activity.slug = slug
                    activity.full_clean()
                    activity.save(update_fields=["slug", "updated_at"])
                counters[domain + "_created"] += 1
            except (ValidationError, PermissionDenied) as exc:
                counters[domain + "_rejected"] += 1
                print("REJECTED", domain, slug, type(exc).__name__, str(exc)[:300])
    print("DOMAIN FOUNDATIONS", "APPLY" if a.apply else "PREVIEW",
          dict(sorted(counters.items())))
    print("Aucune donnée extérieure ni paiement réel n'a été inventé.")


if __name__ == "__main__":
    main()
