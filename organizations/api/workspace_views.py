from django.core.exceptions import PermissionDenied as DjangoPermissionDenied, ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from organizations.models import TeamMembership
from organizations.services import (
    archive_space,
    create_organization,
    restore_space,
    update_organization,
)
from organizations.team_responsibilities import transfer_space_ownership

from .workspace_projection import (
    build_space_workspace,
    has_direct_space_authority,
    workspace_spaces,
)
from .workspace_serializers import (
    SpaceOwnershipTransferSerializer,
    SpaceWorkspaceCreateSerializer,
    SpaceWorkspaceUpdateSerializer,
)


def _raise_domain_error(exc):
    if isinstance(exc, DjangoPermissionDenied):
        raise PermissionDenied(str(exc)) from exc
    if isinstance(exc, DjangoValidationError):
        if hasattr(exc, "message_dict"):
            raise ValidationError(exc.message_dict) from exc
        raise ValidationError(exc.messages) from exc
    raise exc


class SpaceWorkspaceListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        rows = [
            {
                "id": str(space.pk),
                "slug": space.slug,
                "name": space.name,
                "archetype": space.archetype,
                "lifecycle": space.lifecycle,
                "limited_to_activities": not has_direct_space_authority(request.user, space),
                "links": {"workspace": f"/api/v1/organizations/workspaces/{space.slug}/"},
            }
            for space in workspace_spaces(request.user)[:100]
        ]
        response = Response(rows)
        response["Cache-Control"] = "private, no-store"
        return response

    def post(self, request):
        serializer = SpaceWorkspaceCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            space = create_organization(
                creator=request.user,
                **serializer.validated_data,
            )
        except (DjangoPermissionDenied, DjangoValidationError) as exc:
            _raise_domain_error(exc)
        payload = build_space_workspace(request.user, space)
        response = Response(payload, status=status.HTTP_201_CREATED)
        response["Cache-Control"] = "private, no-store"
        return response


class SpaceWorkspaceDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def _space(self, request, slug):
        space = workspace_spaces(request.user).filter(slug=slug).first()
        if space is None:
            raise NotFound()
        return space

    def get(self, request, slug):
        space = self._space(request, slug)
        payload = build_space_workspace(request.user, space)
        if payload is None:
            raise NotFound()
        response = Response(payload)
        response["Cache-Control"] = "private, no-store"
        return response

    def patch(self, request, slug):
        space = self._space(request, slug)
        serializer = SpaceWorkspaceUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            space = update_organization(
                organization=space,
                actor=request.user,
                **serializer.validated_data,
            )
        except (DjangoPermissionDenied, DjangoValidationError) as exc:
            _raise_domain_error(exc)
        response = Response(build_space_workspace(request.user, space))
        response["Cache-Control"] = "private, no-store"
        return response


class SpaceArchiveAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, slug):
        space = get_object_or_404(workspace_spaces(request.user), slug=slug)
        try:
            space = archive_space(space=space, actor=request.user, source="space-api")
        except (DjangoPermissionDenied, DjangoValidationError) as exc:
            _raise_domain_error(exc)
        return Response(build_space_workspace(request.user, space))


class SpaceRestoreAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, slug):
        space = get_object_or_404(workspace_spaces(request.user), slug=slug)
        try:
            space = restore_space(space=space, actor=request.user, source="space-api")
        except (DjangoPermissionDenied, DjangoValidationError) as exc:
            _raise_domain_error(exc)
        return Response(build_space_workspace(request.user, space))


class SpaceOwnershipTransferAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, slug):
        space = get_object_or_404(workspace_spaces(request.user), slug=slug)
        serializer = SpaceOwnershipTransferSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        membership = get_object_or_404(
            TeamMembership.objects.select_related("team__organization", "user"),
            pk=serializer.validated_data["target_membership_id"],
            team__organization=space,
            team__is_default=True,
        )
        try:
            transfer_space_ownership(
                membership=membership,
                actor=request.user,
                relinquish_current_owner=serializer.validated_data["relinquish_current_owner"],
            )
        except (DjangoPermissionDenied, DjangoValidationError) as exc:
            _raise_domain_error(exc)
        return Response(build_space_workspace(request.user, space))
