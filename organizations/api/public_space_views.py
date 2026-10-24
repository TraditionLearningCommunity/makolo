"""Read-only mobile projections for publicly searchable Makolo Spaces.

These views expose less than the Web public passport and never infer a
Mandate, Permission or private association from a public Space.
"""
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from activities.models import Activity
from core.api.projections import projection_envelope
from discovery.api.composition import compose_discovery, project_rows
from organizations.models import Organization, SpaceArchetype, SpaceLifecycle


def _public_spaces():
    return Organization.objects.filter(
        public_profile=True,
        searchable=True,
        lifecycle=SpaceLifecycle.ACTIVE,
    )


def _page_params(query):
    try:
        page = int(query.get("page") or 1)
        page_size = int(query.get("page_size") or 20)
    except (ValueError, TypeError) as exc:
        raise ValidationError({"page": "Pagination invalide."}) from exc
    if page < 1 or page_size < 1:
        raise ValidationError({"page": "Pagination invalide."})
    return page, min(page_size, 30)


def _public_identity(space):
    return {
        "name": space.name,
        "slug": space.slug,
        "description": space.description,
        "archetype": space.archetype,
        "city": space.city,
        "country": space.country,
        "website": space.website,
    }


class PublicSpacesAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        page, page_size = _page_params(request.query_params)
        query = (request.query_params.get("q") or "").strip()[:120]
        category = (request.query_params.get("category") or "").strip()
        city = (request.query_params.get("city") or "").strip()[:120]
        country = (request.query_params.get("country") or "").strip()[:120]
        if category and category not in SpaceArchetype.values:
            raise ValidationError({"category": "Catégorie d’Espace inconnue."})
        spaces = _public_spaces()
        if query:
            spaces = spaces.filter(name__icontains=query)
        if category:
            spaces = spaces.filter(archetype=category)
        if city:
            spaces = spaces.filter(city__icontains=city)
        if country:
            spaces = spaces.filter(country__iexact=country)
        spaces = spaces.order_by("name", "id")
        count = spaces.count()
        start = (page - 1) * page_size
        results = [_public_identity(space) for space in spaces[start:start + page_size]]
        return Response(projection_envelope(
            projection="organizations.public-spaces",
            scope="public",
            data={
                "count": count,
                "categories": [
                    {"value": value, "label": label}
                    for value, label in SpaceArchetype.choices
                ],
                "page": page,
                "page_size": page_size,
                "has_next": start + page_size < count,
                "results": results,
            },
        ))


class PublicSpaceDetailAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, slug):
        space = get_object_or_404(_public_spaces(), slug=slug)
        page, page_size = _page_params(request.query_params)
        # Discovery owns public admission. Never query private Activity rows
        # directly for presentation or equate existence with visibility.
        public_field = compose_discovery({}, profile=None)
        owned_activity_ids = set(
            Activity.objects.filter(space=space).values_list("id", flat=True)
        )
        owned_ids = {str(pk) for pk in owned_activity_ids}
        rows = tuple(
            (family, key, candidate)
            for family, key, candidate in public_field.rows
            if family in {"activity", "service_activity", "funding_activity"}
            and str(
                candidate.get("activity_id")
                if isinstance(candidate, dict)
                else candidate.activity_id
            ) in owned_ids
        )
        start = (page - 1) * page_size
        return Response(projection_envelope(
            projection="organizations.public-space",
            scope="public",
            data={
                "space": _public_identity(space),
                "possibilities": {
                    "count": len(rows),
                    "page": page,
                    "page_size": page_size,
                    "has_next": start + page_size < len(rows),
                    "results": project_rows(rows[start:start + page_size], profile=None),
                },
            },
        ))
