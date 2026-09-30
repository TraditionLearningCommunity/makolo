from django.core.exceptions import PermissionDenied as DjangoPermissionDenied, ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from authorization.constants import PermissionCode
from authorization.models import AuthorityScope
from authorization.selectors import current_mandates
from authorization.services import can
from organizations.models import TeamMembership, TeamMembershipStatus
from organizations.services import (
    add_or_update_member,
    archive_space,
    create_organization,
    find_user_for_team,
    restore_space,
    update_organization,
)
from organizations.team_responsibilities import (
    remove_member_from_space,
    transfer_space_ownership,
    update_member_space_responsibility,
)

from .workspace_projection import (
    build_space_workspace,
    has_direct_space_authority,
    workspace_spaces,
)
from .workspace_serializers import (
    SpaceOwnershipTransferSerializer,
    SpaceTeamMemberCreateSerializer,
    SpaceTeamMemberUpdateSerializer,
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



def _require_team_manage(user, space):
    if not can(user, PermissionCode.SPACE_TEAM_MANAGE, space):
        raise PermissionDenied("Vous ne pouvez pas gérer cette équipe.")


def _team_membership_row(membership, space):
    standard = (
        current_mandates()
        .filter(
            profile=membership.user,
            scope_type=AuthorityScope.SPACE,
            space=space,
            role__is_system=True,
        )
        .order_by("pk")
        .first()
    )
    return {
        "id": str(membership.pk),
        "profile": {
            "id": str(membership.user_id),
            "name": membership.user.full_name or membership.user.username,
            "email": membership.user.email,
        },
        "status": membership.status,
        "responsibility": standard.role.code if standard else None,
    }


class SpaceTeamAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def _space(self, request, slug):
        space = workspace_spaces(request.user).filter(slug=slug).first()
        if space is None:
            raise NotFound()
        _require_team_manage(request.user, space)
        return space

    def get(self, request, slug):
        space = self._space(request, slug)
        memberships = (
            TeamMembership.objects.filter(
                team__organization=space,
                team__is_default=True,
                status=TeamMembershipStatus.ACTIVE,
            )
            .select_related("user")
            .order_by("user__first_name", "user__last_name", "user__email", "pk")
        )
        response = Response([_team_membership_row(row, space) for row in memberships])
        response["Cache-Control"] = "private, no-store"
        return response

    def post(self, request, slug):
        space = self._space(request, slug)
        serializer = SpaceTeamMemberCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            user = find_user_for_team(email=serializer.validated_data["email"])
            membership = add_or_update_member(
                organization=space,
                actor=request.user,
                user=user,
                role=serializer.validated_data["role"],
            )
        except (DjangoPermissionDenied, DjangoValidationError) as exc:
            _raise_domain_error(exc)
        return Response(
            _team_membership_row(membership, space),
            status=status.HTTP_201_CREATED,
        )


class SpaceTeamMemberAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def _objects(self, request, slug, membership_id):
        space = workspace_spaces(request.user).filter(slug=slug).first()
        if space is None:
            raise NotFound()
        _require_team_manage(request.user, space)
        membership = get_object_or_404(
            TeamMembership.objects.select_related("team__organization", "user"),
            pk=membership_id,
            team__organization=space,
            team__is_default=True,
        )
        return space, membership

    def patch(self, request, slug, membership_id):
        space, membership = self._objects(request, slug, membership_id)
        serializer = SpaceTeamMemberUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            update_member_space_responsibility(
                membership=membership,
                actor=request.user,
                role_code=serializer.validated_data["role"],
            )
        except (DjangoPermissionDenied, DjangoValidationError) as exc:
            _raise_domain_error(exc)
        membership.refresh_from_db()
        return Response(_team_membership_row(membership, space))

    def delete(self, request, slug, membership_id):
        _space, membership = self._objects(request, slug, membership_id)
        try:
            remove_member_from_space(membership=membership, actor=request.user)
        except (DjangoPermissionDenied, DjangoValidationError) as exc:
            _raise_domain_error(exc)
        return Response(status=status.HTTP_204_NO_CONTENT)
