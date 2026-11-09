"""Authenticated Project commands. Actions compose Objectives services only."""
from __future__ import annotations

from django.core.exceptions import PermissionDenied, ValidationError
from django.contrib.auth import get_user_model
from authorization.constants import STANDARD_PROJECT_ROLE_CODES
from authorization.models import AuthorityScope, Role
from authorization.selectors import current_mandates
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.api.projections import projection_envelope
from objectives.models import ProjectDossierLink
from objectives.context import resolve_objective_context
from objectives.project_workspace import project_dossier_page
from objectives.selectors import (
    dossiers_for_profile, projects_for_profile,
)
from objectives.services import (
    can_manage_project, can_manage_project_authority, create_dossier,
    grant_project_authority, link_dossier_to_project,
    move_dossier_to_project, set_project_lifecycle,
    revoke_project_authority, unlink_dossier_from_project, update_project,
)
from objectives.api_views import _page_args


def _command_error(exc):
    if isinstance(exc, PermissionDenied):
        return Response({"detail": "Action non autorisée."}, status=status.HTTP_403_FORBIDDEN)
    return Response({"detail": getattr(exc, "messages", [str(exc)])},
                    status=status.HTTP_400_BAD_REQUEST)


class ProjectEditInput(serializers.Serializer):
    title = serializers.CharField(max_length=220, trim_whitespace=True, required=False)
    description = serializers.CharField(allow_blank=True, required=False)
    starts_on = serializers.DateField(allow_null=True, required=False)
    ends_on = serializers.DateField(allow_null=True, required=False)


class ProjectDossierInput(serializers.Serializer):
    action = serializers.ChoiceField(choices=["create", "link"])
    dossier_id = serializers.UUIDField(required=False)
    title = serializers.CharField(max_length=220, trim_whitespace=True, required=False)
    description = serializers.CharField(allow_blank=True, required=False, default="")
    deadline = serializers.DateField(allow_null=True, required=False)

    def validate(self, attrs):
        if attrs["action"] == "link" and not attrs.get("dossier_id"):
            raise serializers.ValidationError({"dossier_id": "Dossier requis."})
        if attrs["action"] == "create" and not attrs.get("title"):
            raise serializers.ValidationError({"title": "Objectif requis."})
        return attrs


class ProjectDossierActionInput(serializers.Serializer):
    action = serializers.ChoiceField(choices=["unlink", "move"])
    target_project_id = serializers.UUIDField(required=False)

    def validate(self, attrs):
        if attrs["action"] == "move" and not attrs.get("target_project_id"):
            raise serializers.ValidationError({"target_project_id": "Projet cible requis."})
        return attrs


class ProjectAuthorityInput(serializers.Serializer):
    action = serializers.ChoiceField(choices=["grant", "revoke"])
    profile_id = serializers.UUIDField(required=False)
    email = serializers.EmailField(required=False)
    role_code = serializers.ChoiceField(
        choices=sorted(STANDARD_PROJECT_ROLE_CODES), required=False,
    )
    mandate_id = serializers.UUIDField(required=False)

    def validate(self, attrs):
        if attrs["action"] == "grant":
            if not attrs.get("role_code") or not (attrs.get("profile_id") or attrs.get("email")):
                raise serializers.ValidationError("Profil et rôle requis.")
            if attrs.get("profile_id") and attrs.get("email"):
                raise serializers.ValidationError("Utilisez un seul identifiant de Profil.")
        elif not attrs.get("mandate_id"):
            raise serializers.ValidationError({"mandate_id": "Mandat requis."})
        return attrs


class ProjectAuthorityAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        context = resolve_objective_context(request.query_params)
        project = get_object_or_404(context.filter(projects_for_profile(request.user)), pk=pk)
        if not can_manage_project_authority(request.user, project):
            return Response({"detail": "Action non autorisée."},
                            status=status.HTTP_403_FORBIDDEN)
        command = ProjectAuthorityInput(data=request.data)
        command.is_valid(raise_exception=True)
        values = command.validated_data
        try:
            if values["action"] == "grant":
                # The actor must already know the exact account to which access
                # is granted. This is not a public member search endpoint.
                users = get_user_model().objects.filter(is_active=True)
                if values.get("profile_id"):
                    person = get_object_or_404(users, pk=values["profile_id"])
                else:
                    matches = list(users.filter(email__iexact=values["email"]).order_by("pk")[:2])
                    if len(matches) != 1:
                        raise ValidationError("Le compte Makolo est introuvable ou ambigu.")
                    person = matches[0]
                role = get_object_or_404(
                    Role.objects.filter(
                        is_active=True, is_system=True,
                        scope_type=AuthorityScope.PROJECT,
                    ), code=values["role_code"],
                )
                mandate = grant_project_authority(
                    actor=request.user, project=project, profile=person, role=role,
                )
            else:
                mandate = get_object_or_404(
                    current_mandates().filter(
                        scope_type=AuthorityScope.PROJECT, project=project,
                    ), pk=values["mandate_id"],
                )
                revoke_project_authority(
                    actor=request.user, project=project, mandate=mandate,
                )
        except (PermissionDenied, ValidationError) as exc:
            return _command_error(exc)
        return Response({
            "kind": "project", "id": str(project.pk),
            "mandate_id": str(mandate.pk), "action": values["action"],
        })


class ProjectLifecycleInput(serializers.Serializer):
    lifecycle = serializers.ChoiceField(
        choices=["draft", "active", "completed", "cancelled", "archived"]
    )


class ProjectDossiersAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        context = resolve_objective_context(request.query_params)
        project = get_object_or_404(context.filter(projects_for_profile(request.user)), pk=pk)
        args = _page_args(request.query_params)
        if args is None:
            return Response({"detail": "Pagination invalide."},
                            status=status.HTTP_400_BAD_REQUEST)
        limit, offset = args
        data = project_dossier_page(request.user, project, limit=limit, offset=offset)
        data["actor_context"] = context.describe(project)
        return Response(projection_envelope(
            projection="objective.project.dossiers.collection",
            data=data,
            generated_at=timezone.now(), scope="authorized",
        ))

    def post(self, request, pk):
        context = resolve_objective_context(request.query_params)
        project = get_object_or_404(context.filter(projects_for_profile(request.user)), pk=pk)
        if not can_manage_project(request.user, project):
            return Response({"detail": "Action non autorisée."},
                            status=status.HTTP_403_FORBIDDEN)
        command = ProjectDossierInput(data=request.data)
        command.is_valid(raise_exception=True)
        values = command.validated_data
        try:
            with transaction.atomic():
                if values["action"] == "create":
                    dossier = create_dossier(
                    actor=request.user, title=values["title"],
                    description=values.get("description", ""),
                    deadline=values.get("deadline"),
                    owner_profile=project.owner_profile, owning_space=project.owning_space,
                    )
                else:
                    dossier = get_object_or_404(
                        context.filter(dossiers_for_profile(request.user)),
                        pk=values["dossier_id"],
                    )
                link_dossier_to_project(actor=request.user, project=project, dossier=dossier)
        except (PermissionDenied, ValidationError) as exc:
            return _command_error(exc)
        return Response({"kind": "dossier", "id": str(dossier.pk),
                         "project_id": str(project.pk)},
                        status=status.HTTP_201_CREATED if values["action"] == "create"
                        else status.HTTP_200_OK)


class ProjectDossierActionAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk, dossier_id):
        context = resolve_objective_context(request.query_params)
        project = get_object_or_404(context.filter(projects_for_profile(request.user)), pk=pk)
        dossier = get_object_or_404(
            dossiers_for_profile(request.user)
            .filter(project_links__project=project, project_links__is_active=True),
            pk=dossier_id,
        )
        action = ProjectDossierActionInput(data=request.data)
        action.is_valid(raise_exception=True)
        values = action.validated_data
        try:
            if values["action"] == "unlink":
                unlink_dossier_from_project(
                    actor=request.user, project=project, dossier=dossier,
                )
            else:
                target = get_object_or_404(
                    context.filter(projects_for_profile(request.user)),
                    pk=values["target_project_id"],
                )
                move_dossier_to_project(
                    actor=request.user, dossier=dossier, target_project=target,
                )
        except (PermissionDenied, ValidationError) as exc:
            return _command_error(exc)
        return Response({"kind": "dossier", "id": str(dossier.pk),
                         "project_id": str(project.pk),
                         "action": values["action"]})


class ProjectLifecycleAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        context = resolve_objective_context(request.query_params)
        project = get_object_or_404(context.filter(projects_for_profile(request.user)), pk=pk)
        command = ProjectLifecycleInput(data=request.data)
        command.is_valid(raise_exception=True)
        try:
            updated = set_project_lifecycle(
                actor=request.user, project=project,
                lifecycle=command.validated_data["lifecycle"],
            )
        except (PermissionDenied, ValidationError) as exc:
            return _command_error(exc)
        return Response({"kind": "project", "id": str(updated.pk),
                         "state": updated.lifecycle})


def edit_project(request, project):
    command = ProjectEditInput(data=request.data)
    command.is_valid(raise_exception=True)
    if not command.validated_data:
        return Response({"detail": "Aucun changement demandé."},
                        status=status.HTTP_400_BAD_REQUEST)
    values = command.validated_data
    try:
        updated = update_project(
            actor=request.user, project=project,
            title=values.get("title", project.title),
            description=values.get("description", project.description),
            starts_on=values.get("starts_on", project.starts_on),
            ends_on=values.get("ends_on", project.ends_on),
        )
    except (PermissionDenied, ValidationError) as exc:
        return _command_error(exc)
    return Response({"kind": "project", "id": str(updated.pk)})
