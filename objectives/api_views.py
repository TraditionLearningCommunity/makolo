from __future__ import annotations

from django.core.exceptions import PermissionDenied, ValidationError as DomainValidationError
from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.api.projections import projection_envelope
from objectives.organizer import build_organizer_page
from objectives.context import resolve_objective_context
from objectives.services import create_dossier, create_project
from organizations.models import Organization
from objectives.readiness import resolve_dossier_readiness
from objectives.selectors import (
    active_assignments_for_dossier,
    dossiers_for_profile,
    projects_for_profile,
    visible_dossiers_for_project,
)


def _date(value):
    return value.isoformat() if value is not None else None


class DossierDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        from objectives.dossier_workspace import dossier_workspace

        context = resolve_objective_context(request.query_params)
        dossier = get_object_or_404(context.filter(dossiers_for_profile(request.user)), pk=pk)
        return Response(projection_envelope(
            projection="objective.dossier.detail",
            data=dossier_workspace(request.user, dossier, actor_context=context),
            generated_at=timezone.now(),
            scope="authorized",
        ))

    def patch(self, request, pk):
        from objectives.dossier_api import edit_dossier

        context = resolve_objective_context(request.query_params)
        dossier = get_object_or_404(context.filter(dossiers_for_profile(request.user)), pk=pk)
        return edit_dossier(request, dossier)


class ProjectDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        from objectives.project_workspace import project_workspace

        context = resolve_objective_context(request.query_params)
        project = get_object_or_404(context.filter(projects_for_profile(request.user)), pk=pk)
        data = project_workspace(request.user, project, actor_context=context)
        return Response(
            projection_envelope(
                projection="objective.project.detail",
                data=data,
                generated_at=timezone.now(),
                scope="authorized",
            )
        )

    def patch(self, request, pk):
        from objectives.project_api import edit_project

        context = resolve_objective_context(request.query_params)
        project = get_object_or_404(context.filter(projects_for_profile(request.user)), pk=pk)
        return edit_project(request, project)


def _page_args(query):
    """Bounded owner collection offset; clients never select another actor."""
    try:
        limit = int(query.get("limit", 24))
        offset = int(query.get("offset", 0))
    except (TypeError, ValueError):
        return None
    if not 1 <= limit <= 50 or offset < 0 or offset > 100000:
        return None
    return limit, offset


class _ObjectiveCollectionAPIView(APIView):
    permission_classes = [IsAuthenticated]
    kind = None

    def get(self, request):
        args = _page_args(request.query_params)
        if args is None:
            return Response(
                {"detail": "Paramètres de liste invalides."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        limit, offset = args
        context = resolve_objective_context(request.query_params)
        if self.kind == "dossier":
            visible = context.filter(dossiers_for_profile(request.user))
        else:
            visible = context.filter(projects_for_profile(request.user))
        page = list(
            visible.order_by("-updated_at", "id")[offset : offset + limit + 1]
        )
        has_more = len(page) > limit
        page = page[:limit]
        entries = []
        for objective in page:
            space = getattr(objective, "owning_space", None)
            entries.append(
                {
                    "kind": self.kind,
                    "id": str(objective.pk),
                    "title": objective.title,
                    "state": objective.lifecycle,
                    "relation": (
                        "mine"
                        if objective.owner_profile_id == request.user.pk
                        else "space"
                        if space is not None
                        else "shared"
                    ),
                    "space": (
                        {"name": space.name, "slug": space.slug}
                        if space is not None
                        else None
                    ),
                    "link": (
                        f"/api/v1/objectives/{self.kind}s/{objective.pk}/"
                    ),
                }
            )
        return Response(
            projection_envelope(
                projection=f"objective.{self.kind}.collection",
                data={
                    "actor": {"type": "profile", "id": str(request.user.pk)},
                    "actor_context": context.describe(),
                    "items": entries,
                    "page": {
                        "offset": offset,
                        "limit": limit,
                        "has_more": has_more,
                        "next_offset": offset + len(entries),
                    },
                },
                generated_at=timezone.now(),
                scope="authorized",
            )
        )


class DossierCollectionAPIView(_ObjectiveCollectionAPIView):
    kind = "dossier"

    def post(self, request):
        return _create_objective(request, self.kind)


class ProjectCollectionAPIView(_ObjectiveCollectionAPIView):
    kind = "project"

    def post(self, request):
        return _create_objective(request, self.kind)


class OrganizerCollectionAPIView(APIView):
    """A viewer-aware, paginated three-kind collection for one local-first index."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        args = _page_args(request.query_params)
        if args is None:
            return Response(
                {"detail": "Paramètres de liste invalides."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        limit, offset = args
        context = resolve_objective_context(request.query_params)
        return Response(projection_envelope(
            projection="objective.organizer.collection",
            data=build_organizer_page(
                request.user, limit=limit, offset=offset, actor_context=context,
            ),
            generated_at=timezone.now(),
            scope="authorized",
        ))


class _ProjectCreateInput(serializers.Serializer):
    title = serializers.CharField(max_length=220, allow_blank=False, trim_whitespace=True)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    owning_space_id = serializers.UUIDField(required=False, allow_null=True)
    starts_on = serializers.DateField(required=False, allow_null=True)
    ends_on = serializers.DateField(required=False, allow_null=True)

    def validate(self, attrs):
        if attrs.get("starts_on") and attrs.get("ends_on") and attrs["starts_on"] > attrs["ends_on"]:
            raise serializers.ValidationError({"ends_on": "La fin doit suivre le début."})
        return attrs


class _DossierCreateInput(serializers.Serializer):
    title = serializers.CharField(max_length=220, allow_blank=False, trim_whitespace=True)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    owning_space_id = serializers.UUIDField(required=False, allow_null=True)
    deadline = serializers.DateField(required=False, allow_null=True)


def _create_objective(request, kind):
    serializer = _ProjectCreateInput if kind == "project" else _DossierCreateInput
    command = serializer(data=request.data)
    command.is_valid(raise_exception=True)
    values = dict(command.validated_data)
    context = resolve_objective_context(request.query_params)
    space_id = values.pop("owning_space_id", None)
    if context.kind == "space":
        # A Space lens cannot silently create a personal objective or place
        # an objective in another Space. Services still enforce real authority.
        space = get_object_or_404(Organization, slug=context.space_slug)
        if space_id is not None and space_id != space.pk:
            raise serializers.ValidationError({
                "owning_space_id": "Le contexte Espace ne correspond pas.",
            })
    else:
        # Creation from the personal entry point is always personal.
        # A client-supplied hidden field must not override the actor lens.
        if space_id is not None:
            raise serializers.ValidationError({
                "owning_space_id": "Le porteur est déduit du point d’entrée.",
            })
        space = None
    common = {
        "actor": request.user,
        "owner_profile": None if space else request.user,
        "owning_space": space,
        **values,
    }
    try:
        obj = create_project(**common) if kind == "project" else create_dossier(**common)
    except PermissionDenied:
        # The owner service is authoritative. A revoked or absent Space
        # mandate must be an explicit refusal, never an unhandled HTTP 500.
        return Response(
            {"detail": "Action non autorisée."},
            status=status.HTTP_403_FORBIDDEN,
        )
    except DomainValidationError as exc:
        return Response(
            {"detail": exc.messages or ["Données invalides."]},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return Response(
        {
            "kind": kind,
            "id": str(obj.pk),
            "link": f"/api/v1/objectives/{kind}s/{obj.pk}/",
        },
        status=status.HTTP_201_CREATED,
    )

