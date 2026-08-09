from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from rest_framework import permissions, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from organizations.models import Organization, OrganizationFollow, OrganizationVerificationStatus
from organizations.services import follow_organization, unfollow_organization, update_follow_preferences

from .serializers import (
    OrganizationFollowCreateSerializer,
    OrganizationFollowPreferenceSerializer,
    OrganizationFollowSerializer,
)


def _raise_service_error(exc):
    if isinstance(exc, DjangoPermissionDenied):
        raise PermissionDenied(str(exc)) from exc
    if isinstance(exc, DjangoValidationError):
        if hasattr(exc, "message_dict"):
            raise ValidationError(exc.message_dict) from exc
        raise ValidationError(exc.messages) from exc
    raise exc


class FollowListCreateAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        follows = OrganizationFollow.objects.filter(user=request.user).select_related("organization")
        return Response(OrganizationFollowSerializer(follows, many=True).data)

    def post(self, request):
        serializer = OrganizationFollowCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        organization = get_object_or_404(
            Organization.objects.filter(public_profile=True).exclude(
                verification_status=OrganizationVerificationStatus.SUSPENDED
            ),
            pk=data.pop("organization_id"),
        )
        try:
            follow = follow_organization(user=request.user, organization=organization, **data)
        except (DjangoPermissionDenied, DjangoValidationError) as exc:
            _raise_service_error(exc)
        follow.refresh_from_db()
        return Response(OrganizationFollowSerializer(follow).data, status=status.HTTP_201_CREATED)


class FollowDetailAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def _follow(self, request, pk):
        return get_object_or_404(
            OrganizationFollow.objects.select_related("organization"),
            pk=pk,
            user=request.user,
        )

    def patch(self, request, pk):
        follow = self._follow(request, pk)
        serializer = OrganizationFollowPreferenceSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            follow = update_follow_preferences(
                follow=follow,
                user=request.user,
                **serializer.validated_data,
            )
        except (DjangoPermissionDenied, DjangoValidationError) as exc:
            _raise_service_error(exc)
        follow.refresh_from_db()
        return Response(OrganizationFollowSerializer(follow).data)

    def delete(self, request, pk):
        follow = self._follow(request, pk)
        try:
            unfollow_organization(follow=follow, user=request.user)
        except (DjangoPermissionDenied, DjangoValidationError) as exc:
            _raise_service_error(exc)
        return Response(status=status.HTTP_204_NO_CONTENT)
