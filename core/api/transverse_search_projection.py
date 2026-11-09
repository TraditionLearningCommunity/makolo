"""Permission-first federation of existing personal owner selectors."""
from django.urls import reverse

from personal_assets.selectors import personal_assets_for_controller
from groups.selectors import groups_for_profile

from access.models import AccessStatus
from commerce.models import CommerceOrder, CommerceOrderStatus
from django.db.models import Q
from journeys.models import JourneyStatus
from trust.credential_models import CredentialType
from trust.credential_selectors import credentials_for_profile
from trust.models import ProofType
from trust.selectors import proofs_for_profile


from core.participant_selectors import (
    participant_access_search,
    participant_accesses,
    participant_journey_search,
    participant_journeys,
)

LIMIT = 24
MAX_LIMIT = 50
MAX_QUERY = 120


def build_profile_search(*, profile, query, offset=0, limit=LIMIT):
    if not query:
        return {
            "actor_context": {"kind": "profile"},
            "query": "",
            "items": [],
            "page": {"count": 0, "offset": offset, "limit": limit, "has_more": False},
            "coverage": {
                "state": "partial",
                "owners": [
                    "journey",
                    "access",
                    "personal_asset",
                    "proof",
                    "credential",
                    "group",
                    "commerce_order",
                ],
            },
        }
    # Both selectors are beneficiary-scoped BEFORE any free text match.
    journeys = participant_journey_search(
        participant_journeys(profile).prefetch_related(None), query
    ).order_by("-created_at", "pk")
    accesses = participant_access_search(
        participant_accesses(profile).prefetch_related(None), query
    ).order_by("-created_at", "pk")
    journey_rows = list(journeys[:offset + limit])
    access_rows = list(accesses[:offset + limit])
    entries = []
    for row in journey_rows:
        is_past = row.status in {
            JourneyStatus.FULFILLED, JourneyStatus.REJECTED,
            JourneyStatus.CANCELLED, JourneyStatus.EXPIRED,
        }
        # The owner detail remains the destination; historical classification
        # does not create another Journey or expose another person's Access.
        entries.append((
            row.created_at, "journey", str(row.pk),
            {
                "source": {"kind": "journey", "id": str(row.pk)},
                "title": row.activity.title,
                "human_type": "Démarche",
                "relation": "Ma démarche",
                "historical": is_past,
                "context": "Historique" if is_past else "En cours",
                "destination": reverse("core:participant-journey-detail", kwargs={"pk": row.pk}),
                "owner_api": reverse("personal-detail-projections:journey-detail", kwargs={"pk": row.pk}),
            },
        ))
    for row in access_rows:
        is_past = row.status in {
            AccessStatus.USED, AccessStatus.CANCELLED, AccessStatus.REVOKED,
            AccessStatus.EXPIRED, AccessStatus.TRANSFERRED,
        }
        entries.append((
            row.created_at, "access", str(row.pk),
            {
                "source": {"kind": "access", "id": str(row.pk)},
                "title": row.activity.title,
                "human_type": "Accès",
                "relation": "Mon accès",
                "historical": is_past,
                "context": "Historique" if is_past else "Accès",
                "destination": reverse("core:participant-access-detail", kwargs={"pk": row.pk}),
                "owner_api": reverse("personal-detail-projections:access-detail", kwargs={"pk": row.pk}),
            },
        ))
    # Personal resources are owned by the document controller, never by Search.
    assets = personal_assets_for_controller(profile).filter(
        title__icontains=query
    ).order_by("-created_at", "pk")
    for row in assets[:offset + limit]:
        entries.append((
            row.created_at, "personal_asset", str(row.pk),
            {
                "source": {"kind": "personal_asset", "id": str(row.pk)},
                "title": row.title,
                "human_type": "Document",
                "relation": "Ma ressource",
                "historical": False,
                "context": "Moi",
                "destination": reverse(
                    "personal_assets:detail", kwargs={"asset_id": row.pk}
                ),
                "owner_api": reverse(
                    "personal-projections:resource-detail", kwargs={"pk": row.pk}
                ),
            },
        ))
    proof_type_matches = [
        value
        for value, label in ProofType.choices
        if query.casefold() in label.casefold() or query.casefold() in value.casefold()
    ]
    proofs = proofs_for_profile(profile).filter(
        Q(journey__activity__title__icontains=query)
        | Q(proof_type__in=proof_type_matches)
    ).order_by("-issued_at", "pk")
    for row in proofs[:offset + limit]:
        entries.append((
            row.issued_at, "proof", str(row.pk),
            {
                "source": {"kind": "proof", "id": str(row.pk)},
                "title": row.get_proof_type_display(),
                "human_type": "Preuve",
                "relation": "Ma preuve",
                "historical": False,
                "context": "Mes ressources",
                "destination": reverse(
                    "trust:proof-detail", kwargs={"proof_id": row.pk}
                ),
                "owner_api": reverse(
                    "personal-projections:proof-detail", kwargs={"pk": row.pk}
                ),
            },
        ))

    credential_type_matches = [
        value
        for value, label in CredentialType.choices
        if query.casefold() in label.casefold() or query.casefold() in value.casefold()
    ]
    credentials = credentials_for_profile(profile).filter(
        Q(title__icontains=query)
        | Q(activity__title__icontains=query)
        | Q(issuer_space__name__icontains=query)
        | Q(issuer_profile__first_name__icontains=query)
        | Q(issuer_profile__last_name__icontains=query)
        | Q(issuer_profile__username__icontains=query)
        | Q(credential_type__in=credential_type_matches)
    ).order_by("-issued_at", "pk")
    for row in credentials[:offset + limit]:
        entries.append((
            row.issued_at, "credential", str(row.pk),
            {
                "source": {"kind": "credential", "id": str(row.pk)},
                "title": row.title,
                "human_type": "Titre",
                "relation": "Mon titre",
                "historical": False,
                "context": "Mes ressources",
                "destination": reverse(
                    "trust:credential-detail", kwargs={"credential_id": row.pk}
                ),
                "owner_api": reverse(
                    "personal-projections:title-detail", kwargs={"pk": row.pk}
                ),
            },
        ))

    groups = groups_for_profile(profile).filter(
        space__isnull=True,
        name__icontains=query
    ).order_by("-created_at", "pk")
    for row in groups[:offset + limit]:
        entries.append((
            row.created_at, "group", str(row.pk),
            {
                "source": {"kind": "group", "id": str(row.pk)},
                "title": row.name,
                "human_type": "Groupe",
                "relation": "Mon collectif",
                "historical": False,
                "context": "Moi",
                "destination": reverse(
                    "groups:detail", kwargs={"slug": row.slug}
                ),
                "owner_api": reverse(
                    "personal-projections:group-detail", kwargs={"pk": row.pk}
                ),
            },
        ))
    orders = CommerceOrder.objects.filter(buyer=profile).filter(
        Q(reference__icontains=query)
        | Q(journey__activity__title__icontains=query)
    ).select_related("journey__activity").order_by("-created_at", "pk")
    for order in orders[:offset + limit]:
        completed = (
            order.status == CommerceOrderStatus.CANCELLED
            and order.cancelled_at is not None
        )
        entries.append((
            order.created_at, "commerce_order", str(order.pk),
            {
                "source": {"kind": "commerce_order", "id": str(order.pk)},
                "title": f"Commande {order.reference}",
                "human_type": "Commande",
                "relation": "Mon achat",
                "context": "Historique" if completed else "Commande",
                "historical": completed,
                "destination": reverse(
                    "core:participant-commerce-order-detail",
                    kwargs={"pk": order.pk},
                ),
                "owner_api": reverse(
                    "personal-projections:commerce-order-detail",
                    kwargs={"order_id": order.pk},
                ),
            },
        ))
    entries.sort(key=lambda row: (row[0], row[1], row[2]), reverse=True)
    total = (
        journeys.count()
        + accesses.count()
        + assets.count()
        + proofs.count()
        + credentials.count()
        + groups.count()
        + orders.count()
    )
    selected = [row[3] for row in entries[offset:offset + limit]]
    return {
        "actor_context": {"kind": "profile"},
        "query": query,
        "items": selected,
        "page": {
            "count": total, "offset": offset, "limit": limit,
            "has_more": offset + len(selected) < total,
        },
        "coverage": {
            "state": "partial",
            "owners": [
                "journey",
                "access",
                "personal_asset",
                "proof",
                "credential",
                "group",
                "commerce_order",
            ],
        },
    }
