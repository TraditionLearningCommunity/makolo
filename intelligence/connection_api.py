"""HTTP owner endpoints for configured Intelligence provider connections.

The generic Z16/M7 projection remains read-only. These owner endpoints
expose only explicitly supported fixed providers, not arbitrary OAuth scopes.
"""
from __future__ import annotations

from core.api.privacy import PrivateNoStoreMixin
from django.core.exceptions import ImproperlyConfigured, ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status

from authorization.constants import PermissionCode
from authorization.selectors import has_direct_space_permission
from authorization.services import can
from intelligence.demo_connections import demo_offers, create_demo_connection
from intelligence.connection_management import (
    catalog, create_connection, disconnect_connection, update_connection,
)
from intelligence.interoperability import project_provider_connection
from intelligence.models import ProviderConnection, ProviderScope
from organizations.models import Organization


def _response(data, *, status_code=200):
    response = Response(data, status=status_code)
    response["Cache-Control"] = "private, no-store"
    return response


def _validation_error(error):
    if hasattr(error, "message_dict"):
        return ValidationError(error.message_dict)
    return ValidationError(error.messages)


class _ScopedIntelligenceConnections(PrivateNoStoreMixin):
    scope = None

    def _owner(self, request, *, slug=None):
        if self.scope == ProviderScope.PROFILE:
            return {"scope": ProviderScope.PROFILE, "profile__user": request.user}, None
        if self.scope == ProviderScope.SPACE:
            space = Organization.objects.filter(slug=slug).first()
            if space is None or not has_direct_space_permission(
                request.user, space, PermissionCode.SPACE_MANAGE,
            ):
                raise NotFound()
            return {"scope": ProviderScope.SPACE, "space": space}, space
        if self.scope == ProviderScope.PLATFORM:
            if not can(request.user, PermissionCode.PLATFORM_MANAGE):
                raise PermissionDenied("Autorité Platform requise.")
            return {"scope": ProviderScope.PLATFORM}, None
        raise NotFound()


class _ConnectionCatalog(_ScopedIntelligenceConnections, APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, slug=None):
        self._owner(request, slug=slug)
        return _response({"offers": catalog() + demo_offers()})

    def post(self, request, slug=None):
        _, space = self._owner(request, slug=slug)
        if isinstance(request.data, dict) and str(request.data.get("provider", "")).startswith("demo-"):
            try:
                connection, _ = create_demo_connection(
                    actor=request.user, scope=self.scope, space=space,
                    provider=request.data["provider"], consent=request.data.get("consent"),
                )
            except DjangoValidationError as exc:
                raise _validation_error(exc) from exc
            connection = ProviderConnection.objects.prefetch_related("routes").get(pk=connection.pk)
            return _response(project_provider_connection(connection, manageable=True), status_code=201)
        try:
            connection = create_connection(
                actor=request.user, scope=self.scope,
                payload=request.data, space=space,
            )
        except DjangoValidationError as exc:
            raise _validation_error(exc) from exc
        except (ImproperlyConfigured, ValueError):
            return _response(
                {"detail": "La configuration sécurisée des connexions est indisponible."},
                status_code=503,
            )
        connection = ProviderConnection.objects.prefetch_related("routes").get(pk=connection.pk)
        return _response(project_provider_connection(connection, manageable=True), status_code=201)


class _ConnectionDetail(_ScopedIntelligenceConnections, APIView):
    permission_classes = [IsAuthenticated]

    def _connection(self, request, connection_id, slug=None):
        owner, _ = self._owner(request, slug=slug)
        return get_object_or_404(
            ProviderConnection.objects.filter(**owner).prefetch_related("routes"),
            pk=connection_id,
        )

    def get(self, request, connection_id, slug=None):
        return _response(project_provider_connection(
            self._connection(request, connection_id, slug=slug), manageable=True,
        ))

    def patch(self, request, connection_id, slug=None):
        connection = self._connection(request, connection_id, slug=slug)
        try:
            connection = update_connection(actor=request.user, connection=connection, payload=request.data)
        except DjangoValidationError as exc:
            raise _validation_error(exc) from exc
        except (ImproperlyConfigured, ValueError):
            return _response(
                {"detail": "La configuration sécurisée des connexions est indisponible."},
                status_code=503,
            )
        connection = ProviderConnection.objects.prefetch_related("routes").get(pk=connection.pk)
        return _response(project_provider_connection(connection, manageable=True))

    def delete(self, request, connection_id, slug=None):
        connection = self._connection(request, connection_id, slug=slug)
        disconnect_connection(actor=request.user, connection=connection)
        return _response({}, status_code=status.HTTP_204_NO_CONTENT)


class ProfileIntelligenceConnectionsAPIView(_ConnectionCatalog):
    scope = ProviderScope.PROFILE


class ProfileIntelligenceConnectionAPIView(_ConnectionDetail):
    scope = ProviderScope.PROFILE


class SpaceIntelligenceConnectionsAPIView(_ConnectionCatalog):
    scope = ProviderScope.SPACE


class SpaceIntelligenceConnectionAPIView(_ConnectionDetail):
    scope = ProviderScope.SPACE


class PlatformIntelligenceConnectionsAPIView(_ConnectionCatalog):
    scope = ProviderScope.PLATFORM


class PlatformIntelligenceConnectionAPIView(_ConnectionDetail):
    scope = ProviderScope.PLATFORM
