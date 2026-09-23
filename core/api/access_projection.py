from __future__ import annotations

from django.urls import reverse

from access.models import AccessStatus, CredentialStatus
from core.participant_selectors import (
    participant_access_search,
    participant_active_accesses,
    participant_purchased_accesses_for_others,
)
from core.product_language import access_status_label, vocabulary_for


ACCESS_RELATION_BENEFICIARY = "beneficiary"
ACCESS_RELATION_PURCHASED_FOR_OTHER = "purchased_for_other"
ACCESS_RELATIONS = {
    ACCESS_RELATION_BENEFICIARY,
    ACCESS_RELATION_PURCHASED_FOR_OTHER,
}
ACCESS_DEFAULT_LIMIT = 24
ACCESS_MAX_LIMIT = 50
ACCESS_SEARCH_MAX_LENGTH = 120


def _iso(value):
    return value.isoformat() if value is not None else None


def _date(value):
    return value.isoformat() if value is not None else None


def _primary_place(occurrence):
    if occurrence is None:
        return None
    links = list(occurrence.place_links.all())
    primary = next((link for link in links if link.role == "primary"), None)
    link = primary or (links[0] if links else None)
    if link is None:
        return None
    return {
        "name": link.place.name or None,
        "locality": link.place.locality or None,
    }


def _occurrence_payload(occurrence):
    if occurrence is None:
        return None
    timing = {
        "kind": occurrence.timing_kind,
        "timezone": occurrence.timezone,
        "start_date": _date(occurrence.start_date),
        "end_date": _date(occurrence.end_date),
    }
    if occurrence.start_at is not None:
        timing["start_at"] = _iso(occurrence.start_at)
    if occurrence.end_at is not None:
        timing["end_at"] = _iso(occurrence.end_at)
    return {
        "kind": "occurrence",
        "id": str(occurrence.pk),
        "timing": {key: value for key, value in timing.items() if value is not None},
        "place": _primary_place(occurrence),
    }


def _active_credential(access):
    return next(
        (
            credential
            for credential in access.credentials.all()
            if credential.status == CredentialStatus.ACTIVE
        ),
        None,
    )


def _credential_summary(access):
    credential = _active_credential(access)
    presentable = credential is not None and access.status == AccessStatus.VALID
    return {
        "available": credential is not None,
        "type": credential.credential_type if credential is not None else None,
        "presentable": presentable,
    }


def _holder_payload(access):
    return {
        "kind": "profile" if access.beneficiary_id else "external_beneficiary",
        "display_name": access.beneficiary_display_name,
    }


def _access_item(access, *, profile, relationship):
    workflow = access.journey.workflow if access.journey_id else None
    vocabulary = vocabulary_for(activity=access.activity, workflow=workflow)
    credential = _credential_summary(access)

    links = {
        "detail": reverse(
            "personal-detail-projections:access-detail",
            kwargs={"pk": access.pk},
        )
    }
    capabilities = []
    if credential["presentable"]:
        links["credential"] = reverse(
            "personal-projections:access-credential",
            kwargs={"pk": access.pk},
        )
        capabilities.append("present_credential")

    journey = None
    if relationship == ACCESS_RELATION_BENEFICIARY and access.journey_id:
        journey = {"kind": "journey", "id": str(access.journey_id)}

    return {
        "identity": {"kind": "access", "id": str(access.pk)},
        "relationship": relationship,
        "state": {
            "code": access.status,
            "label": access_status_label(access.status),
        },
        "representation": {
            "vertical": vocabulary.vertical,
            "label": vocabulary.access_noun,
        },
        "activity": {
            "kind": "activity",
            "id": str(access.activity_id),
            "title": access.activity.title,
        },
        "occurrence": _occurrence_payload(access.occurrence),
        "validity": {
            "from": _iso(access.valid_from),
            "until": _iso(access.valid_until),
        },
        "holder": (
            _holder_payload(access)
            if relationship == ACCESS_RELATION_PURCHASED_FOR_OTHER
            else None
        ),
        "journey": journey,
        "credential": credential,
        "capabilities": capabilities,
        "links": links,
    }


def _with_projection_relations(queryset):
    return queryset.select_related(
        "activity__transport_service",
        "activity__service_details",
        "activity__funding_details",
    )


def build_personal_accesses_data(
    profile,
    *,
    observed_at,
    relationship=ACCESS_RELATION_BENEFICIARY,
    query="",
    limit=ACCESS_DEFAULT_LIMIT,
    offset=0,
):
    query = (query or "").strip()

    if relationship == ACCESS_RELATION_BENEFICIARY:
        queryset = participant_active_accesses(profile, at=observed_at)
        queryset = participant_access_search(queryset, query)
        queryset = queryset.order_by("occurrence__start_at", "-created_at", "id")
    elif relationship == ACCESS_RELATION_PURCHASED_FOR_OTHER:
        queryset = participant_purchased_accesses_for_others(profile)
        queryset = participant_access_search(
            queryset,
            query,
            include_external_holder=True,
        )
        queryset = queryset.order_by("-created_at", "id")
    else:
        raise ValueError("Relation Access inconnue.")

    queryset = _with_projection_relations(queryset)
    total = queryset.count()
    rows = list(queryset[offset : offset + limit])
    base = reverse("personal-projections:accesses")

    return {
        "relationship": relationship,
        "query": query or None,
        "items": [
            _access_item(row, profile=profile, relationship=relationship)
            for row in rows
        ],
        "page": {
            "count": total,
            "offset": offset,
            "limit": limit,
            "has_more": offset + len(rows) < total,
        },
        "links": {
            "self": base,
            "mine": base,
            "purchased_for_others": (
                f"{base}?relationship={ACCESS_RELATION_PURCHASED_FOR_OTHER}"
            ),
        },
    }


def build_personal_access_credential_data(*, profile, access):
    relationship = (
        ACCESS_RELATION_BENEFICIARY
        if access.beneficiary_id == profile.pk
        else ACCESS_RELATION_PURCHASED_FOR_OTHER
    )
    credential = _active_credential(access)
    if access.status != AccessStatus.VALID or credential is None:
        return None

    from access.services import render_access_credential

    return {
        "access": {"kind": "access", "id": str(access.pk)},
        "relationship": relationship,
        "holder": (
            _holder_payload(access)
            if relationship == ACCESS_RELATION_PURCHASED_FOR_OTHER
            else None
        ),
        "representation": {
            "credential_type": credential.credential_type,
            "payload": render_access_credential(credential),
            "issued_at": _iso(credential.issued_at),
        },
    }
