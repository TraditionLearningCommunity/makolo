from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.cache import patch_vary_headers

from rest_framework.exceptions import NotFound, ValidationError
from django.core.exceptions import ValidationError as DomainValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.api.projections import projection_envelope
from discovery.models import (
    ActivityBookmark,
    DiscoveryWatch,
    DiscoveryWatchStatus,
)
from discovery.services import (
    build_recommendations,
    build_trending,
    public_discovery_events,
    serialize_event,
)
from discovery.watches import execute_watch, normalize_watch_criteria, ensure_discovery_watch
from objectives.models import Dossier
from organizations.api.workspace_projection import workspace_spaces

from .composition import (
    compose_discovery,
    paginated_projection,
    parse_page_params,
    project_rows,
    spatial_index_from_rows,
    spatial_discovery_projection,
    _public_occurrence_facts_for_rows,
    set_saved_state,
    detail_projection,
)


class PrivateDiscoveryResponseBoundary:
    """An API response may depend on viewer/owner authority at every request.

    Do not let a browser, proxy or shared HTTP cache reuse a personal field,
    Watch, Bookmark, N2 detail, error response or signed continuation.
    """

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "private, no-store"
        patch_vary_headers(response, ("Authorization", "Cookie"))
        return response


MAX_MAP_POINTS = 100


def _scope_for(request, *, space=None):
    if space is not None:
        return "space"
    return "personal" if getattr(request.user, "is_authenticated", False) else "public"


def _exploration_space(request):
    """Resolve a requested Space from current server authority, never from a client profile ID."""
    context = request.query_params.get("context")
    slug = request.query_params.get("space")
    if context not in (None, "", "space", "personal", "public"):
        raise ValidationError({"context": ["Contexte Découvrir invalide."]})
    if context == "personal" and not getattr(request.user, "is_authenticated", False):
        from rest_framework.exceptions import NotAuthenticated
        raise NotAuthenticated()
    if context == "public" and getattr(request.user, "is_authenticated", False):
        raise ValidationError({"context": ["Le contexte public ne remplace pas un Profil authentifié."]})
    if context != "space":
        if slug:
            raise ValidationError({"space": ["Un Space exige context=space."]})
        return None
    if not isinstance(slug, str) or not slug.strip():
        raise ValidationError({"space": ["Space requis."]})
    if not getattr(request.user, "is_authenticated", False):
        from rest_framework.exceptions import NotAuthenticated
        raise NotAuthenticated()
    return get_object_or_404(workspace_spaces(request.user), slug=slug)


def _reject_profile_override(request):
    if "profile_id" in request.query_params:
        raise ValidationError(
            {"profile_id": ["Discovery personnel utilise uniquement request.user."]}
        )


from .throttles import DiscoveryClarifyThrottle, DiscoveryResearchThrottle


class DiscoveryResearchAPIView(PrivateDiscoveryResponseBoundary, APIView):
    """Optional external leads; never a canonical Discovery item or GET side effect."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [DiscoveryResearchThrottle]

    def post(self, request):
        from discovery.assistance import research_discovery_sources

        if not isinstance(request.data, dict) or set(request.data) != {"q"}:
            raise ValidationError({"q": ["Recherche invalide."]})
        try:
            result = research_discovery_sources(
                actor=request.user, text=request.data["q"],
            )
        except ValueError as exc:
            raise ValidationError({"q": [str(exc)]}) from exc
        response = Response(projection_envelope(
            projection="discovery.source-leads",
            scope="personal", data=result,
        ))
        response["Cache-Control"] = "private, no-store"
        return response


class DiscoveryClarifyAPIView(PrivateDiscoveryResponseBoundary, APIView):
    """Explicit, authenticated Discovery clarification. Never a billable GET."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [DiscoveryClarifyThrottle]

    def post(self, request):
        from discovery.assistance import clarify_discovery_search

        if not isinstance(request.data, dict) or set(request.data) != {"criteria"}:
            raise ValidationError({"criteria": ["Contrat de recherche invalide."]})
        try:
            result = clarify_discovery_search(
                actor=request.user, criteria=request.data["criteria"],
            )
        except ValueError as exc:
            raise ValidationError({"criteria": [str(exc)]}) from exc
        response = Response(
            projection_envelope(
                projection="discovery.clarification",
                scope="personal",
                data=result,
            )
        )
        response["Cache-Control"] = "private, no-store"
        return response


class DiscoveryItemsAPIView(PrivateDiscoveryResponseBoundary, APIView):
    """Canonical mature Discovery collection.

    The legacy Event-only mobile feed remains under /api/v1/events/discover/.
    This endpoint represents the same multi-family possibility field as the
    mature Web surface.
    """

    permission_classes = [AllowAny]

    def get(self, request):
        _reject_profile_override(request)
        space = _exploration_space(request)
        try:
            data = paginated_projection(
                request.query_params,
                profile=request.user,
                space=space,
            )
        except DjangoValidationError as exc:
            raise ValidationError({"discovery": exc.messages}) from exc
        return Response(
            projection_envelope(
                projection="discovery.items",
                scope=_scope_for(request, space=space),
                data=data,
            )
        )


class DiscoveryItemDetailAPIView(PrivateDiscoveryResponseBoundary, APIView):
    permission_classes = [AllowAny]

    def get(self, request, family, item_id):
        _reject_profile_override(request)
        space = _exploration_space(request)
        projection = detail_projection(
            family,
            item_id,
            profile=request.user,
            space=space,
        )
        if projection is None:
            raise NotFound("Possibilité introuvable.")
        payload = {"item": projection}
        if space is not None:
            payload.update({
                "actor": {"type": "space", "id": str(space.pk)},
                "viewer": {"type": "profile", "id": str(request.user.pk)},
            })
        return Response(
            projection_envelope(
                projection="discovery.item",
                scope=_scope_for(request, space=space),
                data=payload,
            )
        )


class DiscoveryItemSavedAPIView(PrivateDiscoveryResponseBoundary, APIView):
    """Explicit conservation, distinct from Interest, Watch and engagement."""

    permission_classes = [IsAuthenticated]

    def put(self, request, family, item_id):
        if request.query_params.get("context") == "space" or request.query_params.get("space"):
            raise ValidationError({"context": ["Cet enregistrement appartient au Profil, pas au Space."]})
        projection = set_saved_state(
            family,
            item_id,
            profile=request.user,
            save=True,
        )
        if projection is None:
            raise NotFound("Possibilité introuvable.")
        return Response(
            projection_envelope(
                projection="discovery.saved",
                data={"item": projection},
            )
        )

    def delete(self, request, family, item_id):
        if request.query_params.get("context") == "space" or request.query_params.get("space"):
            raise ValidationError({"context": ["Cet enregistrement appartient au Profil, pas au Space."]})
        projection = set_saved_state(
            family,
            item_id,
            profile=request.user,
            save=False,
        )
        if projection is None:
            raise NotFound("Possibilité introuvable.")
        return Response(
            projection_envelope(
                projection="discovery.saved",
                data={"item": projection},
            )
        )


class DiscoveryMapAPIView(PrivateDiscoveryResponseBoundary, APIView):
    """Public/private-viewer map projection from the same Discovery field."""

    permission_classes = [AllowAny]

    def get(self, request):
        _reject_profile_override(request)
        space = _exploration_space(request)
        candidate_profile = None if space is not None else request.user
        try:
            composition = compose_discovery(
                request.query_params,
                profile=candidate_profile,
            )
        except DjangoValidationError as exc:
            raise ValidationError({"discovery": exc.messages}) from exc
        # Spatial presentation of the *same admitted candidates* as Discovery.
        # Opt-in keeps the legacy 100-point API stable for existing consumers.
        if request.query_params.get("spatial") == "1":
            if request.query_params.get("details") == "1":
                return Response(spatial_discovery_projection(
                    composition.rows,
                    profile=candidate_profile,
                    space=space,
                    viewer=request.user if space is not None else None,
                ))
            # Compatibility path for existing Map consumers.
            return Response(spatial_index_from_rows(composition.rows))

        points = []
        for family, _, candidate in composition.rows:
            if family != "activity":
                continue
            payload = candidate.to_map_dict()
            if payload is not None:
                points.append(payload)
            if len(points) >= MAX_MAP_POINTS:
                break
        return Response(
            {
                "count": len(points),
                "total_results": len(composition.rows),
                "timezone": composition.timezone_name,
                "nearby_active": composition.nearby_active,
                "results": points,
            }
        )


class DiscoveryForYouAPIView(PrivateDiscoveryResponseBoundary, APIView):
    """Historical Event-compatibility surface, deliberately not Z3 ranking."""

    permission_classes = [AllowAny]

    def get(self, request):
        recommendations = build_recommendations(request.user, limit=24)
        trending = build_trending(limit=12)
        return Response(
            {
                "scope": "event_compatibility",
                "recommendations": [
                    serialize_event(
                        row["event"],
                        reason=" · ".join(row["reasons"]),
                        score=row["score"],
                    )
                    for row in recommendations
                ],
                "trending": [
                    serialize_event(row["event"], score=row["score"])
                    for row in trending
                ],
            }
        )


class BookmarkListCreateAPIView(PrivateDiscoveryResponseBoundary, APIView):
    """Legacy Event-shaped bookmark API backed by canonical ActivityBookmark."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        bookmarks = ActivityBookmark.objects.filter(
            user=request.user,
            activity__event_vertical__isnull=False,
        ).select_related(
            "activity",
            "activity__event_vertical",
            "activity__event_vertical__category",
            "activity__event_vertical__venue",
        )[:100]
        return Response(
            [
                {
                    "id": str(bookmark.pk),
                    "created_at": bookmark.created_at,
                    "event": serialize_event(bookmark.activity.event_vertical),
                }
                for bookmark in bookmarks
            ]
        )

    def post(self, request):
        event_id = request.data.get("event_id")
        event = get_object_or_404(public_discovery_events(), pk=event_id)
        bookmark, created = ActivityBookmark.objects.get_or_create(
            user=request.user,
            activity=event.activity,
        )
        return Response(
            {
                "id": str(bookmark.pk),
                "created": created,
                "event": serialize_event(event),
            },
            status=201 if created else 200,
        )


class BookmarkDetailAPIView(PrivateDiscoveryResponseBoundary, APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, event_id):
        event = get_object_or_404(public_discovery_events(), pk=event_id)
        ActivityBookmark.objects.filter(
            user=request.user,
            activity=event.activity,
        ).delete()
        return Response(status=204)


def _owned_watch(request, watch_id):
    return get_object_or_404(
        DiscoveryWatch.objects.select_related("dossier"),
        pk=watch_id,
        owner=request.user,
    )


def _watch_payload(watch):
    return {
        "id": str(watch.pk),
        "name": watch.name,
        "status": watch.status,
        "criteria": dict(watch.criteria),
        "dossier": (
            {
                "id": str(watch.dossier_id),
                "title": watch.dossier.title,
            }
            if watch.dossier_id
            else None
        ),
        "created_at": watch.created_at.isoformat(),
        "updated_at": watch.updated_at.isoformat(),
    }


def _normalize_watch_or_error(raw):
    try:
        return normalize_watch_criteria(raw)
    except DomainValidationError as exc:
        raise ValidationError({"criteria": exc.messages}) from exc


def _resolve_personal_dossier(request, raw_id):
    if raw_id in (None, ""):
        return None
    try:
        dossier = Dossier.objects.filter(
            pk=raw_id,
            owner_profile=request.user,
            owning_space__isnull=True,
        ).first()
    except (ValueError, TypeError, DomainValidationError) as exc:
        raise ValidationError({"dossier_id": ["Identifiant de Dossier invalide."]}) from exc
    if dossier is None:
        raise ValidationError(
            {"dossier_id": ["Dossier personnel introuvable."]}
        )
    return dossier


class DiscoveryWatchListCreateAPIView(PrivateDiscoveryResponseBoundary, APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        watches = (
            DiscoveryWatch.objects.filter(owner=request.user)
            .select_related("dossier")
            .order_by("-updated_at", "id")[:100]
        )
        return Response(
            projection_envelope(
                projection="discovery.watches",
                data={"results": [_watch_payload(watch) for watch in watches]},
            )
        )

    def post(self, request):
        name = str(request.data.get("name") or "").strip()
        if not name or len(name) > 140:
            raise ValidationError({"name": ["Le nom de la Veille doit contenir entre 1 et 140 caractères."]})
        criteria = _normalize_watch_or_error(request.data.get("criteria"))
        dossier = _resolve_personal_dossier(
            request, request.data.get("dossier_id"),
        )
        watch, created = ensure_discovery_watch(
            owner=request.user, name=name, criteria=criteria, dossier=dossier,
        )
        return Response(
            projection_envelope(
                projection="discovery.watch",
                data={"watch": _watch_payload(watch), "created": created},
            ),
            status=201 if created else 200,
        )


class DiscoveryWatchDetailAPIView(PrivateDiscoveryResponseBoundary, APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, watch_id):
        watch = _owned_watch(request, watch_id)
        return Response(
            projection_envelope(
                projection="discovery.watch",
                data={"watch": _watch_payload(watch)},
            )
        )

    def patch(self, request, watch_id):
        watch = _owned_watch(request, watch_id)
        if "name" in request.data:
            name = str(request.data.get("name") or "").strip()
            if not name or len(name) > 140:
                raise ValidationError(
                    {"name": ["Le nom de la Veille doit contenir entre 1 et 140 caractères."]}
                )
            watch.name = name
        if "criteria" in request.data:
            watch.criteria = _normalize_watch_or_error(
                request.data.get("criteria")
            )
        if "status" in request.data:
            status = str(request.data.get("status") or "").strip()
            if status not in DiscoveryWatchStatus.values:
                raise ValidationError(
                    {"status": ["État de Veille invalide."]}
                )
            watch.status = status
        if "dossier_id" in request.data:
            watch.dossier = _resolve_personal_dossier(
                request,
                request.data.get("dossier_id"),
            )
        try:
            watch.save()
        except DomainValidationError as exc:
            raise ValidationError({"watch": exc.messages}) from exc
        return Response(
            projection_envelope(
                projection="discovery.watch",
                data={"watch": _watch_payload(watch)},
            )
        )

    def delete(self, request, watch_id):
        watch = _owned_watch(request, watch_id)
        watch.delete()
        return Response(status=204)


class DiscoveryWatchResultsAPIView(PrivateDiscoveryResponseBoundary, APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, watch_id):
        watch = _owned_watch(request, watch_id)
        result = execute_watch(
            watch.criteria,
            profile=request.user,
        )
        rows = [
            ("activity", item.candidate_key, item)
            for item in result.items
        ]
        rows.extend(
            (
                "service_activity",
                item["candidate_key"],
                item,
            )
            for item in result.service_items
        )
        page, page_size = parse_page_params(request.query_params)
        start = (page - 1) * page_size
        end = start + page_size
        page_rows = tuple(rows[start:end])
        projected = project_rows(
            page_rows,
            profile=request.user,
        )
        for item in projected:
            item["watch"] = {
                "state": "covered",
                "watch_id": str(watch.pk),
            }
        data = {
            "watch": _watch_payload(watch),
            "supported_families": ["activity", "service_activity"],
            "count": len(rows),
            "page": page,
            "page_size": page_size,
            "has_next": end < len(rows),
            "has_previous": page > 1 and bool(rows),
            "timezone": result.timezone_name,
            "nearby_active": result.nearby_active,
            "results": projected,
        }
        return Response(
            projection_envelope(
                projection="discovery.watch-results",
                data=data,
            )
        )
