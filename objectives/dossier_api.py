"""Owner-backed Dossier commands: no client-side business transition rules.

Each mutation resolves its operands under the current viewer and delegates
to the existing Objectives service which locks/revalidates authority.
"""
from __future__ import annotations

from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from authorization.models import AuthorityScope, Role
from objectives.models import DossierJourneyDependencyState
from objectives.context import resolve_objective_context
from objectives.selectors import (
    active_assignments_for_dossier, active_project_for_dossier,
    collaboration_candidates_for_dossier, current_dossier_authority_mandates,
    dossiers_for_profile, linkable_journeys_for_profile, projects_for_profile,
    visible_dependencies_for_profile, visible_linked_journeys,
)
from objectives.services import (
    add_dependency, assign_dossier, can_manage_dossier,
    can_manage_dossier_authority, can_manage_project,
    grant_dossier_authority, link_dossier_to_project, link_journey,
    move_dossier_to_project, remove_dependency, revoke_dossier_authority,
    set_dossier_lifecycle, unassign_dossier, unlink_dossier_from_project,
    unlink_journey, update_dossier, waive_dependency,
)


class DossierEditInput(serializers.Serializer):
    title = serializers.CharField(max_length=220, trim_whitespace=True, required=False)
    description = serializers.CharField(allow_blank=True, required=False)
    deadline = serializers.DateField(allow_null=True, required=False)


class DossierActionInput(serializers.Serializer):
    action = serializers.ChoiceField(choices=(
        "link_journey", "unlink_journey", "add_dependency",
        "remove_dependency", "waive_dependency",
        "assignment_add", "assignment_remove",
        "mandate_grant", "mandate_revoke",
        "lifecycle", "project_set",
    ))
    journey_id = serializers.UUIDField(required=False)
    dependent_link_id = serializers.UUIDField(required=False)
    required_link_id = serializers.UUIDField(required=False)
    dependency_id = serializers.UUIDField(required=False)
    reason = serializers.CharField(max_length=280, required=False)
    assignment_id = serializers.UUIDField(required=False)
    assignee_id = serializers.UUIDField(required=False)
    mandate_id = serializers.UUIDField(required=False)
    profile_id = serializers.UUIDField(required=False)
    role_id = serializers.UUIDField(required=False)
    lifecycle = serializers.ChoiceField(
        choices=("draft", "active", "completed", "cancelled", "archived"),
        required=False,
    )
    project_id = serializers.UUIDField(allow_null=True, required=False)

    def validate(self, attrs):
        action = attrs["action"]
        required = {
            "link_journey": ("journey_id",),
            "unlink_journey": ("journey_id",),
            "add_dependency": ("dependent_link_id", "required_link_id"),
            "remove_dependency": ("dependency_id",),
            "waive_dependency": ("dependency_id", "reason"),
            "assignment_add": ("assignee_id",),
            "assignment_remove": ("assignment_id",),
            "mandate_grant": ("profile_id", "role_id"),
            "mandate_revoke": ("mandate_id",),
            "lifecycle": ("lifecycle",),
            "project_set": ("project_id",),
        }[action]
        missing = [key for key in required if key not in attrs]
        if missing:
            raise serializers.ValidationError({
                key: "Champ obligatoire pour cette action." for key in missing
            })
        if action == "waive_dependency" and not attrs["reason"].strip():
            raise serializers.ValidationError({"reason": "Une raison est requise."})
        return attrs


def _domain_error(exc):
    if isinstance(exc, PermissionDenied):
        return Response({"detail": "Action non autorisée."},
                        status=status.HTTP_403_FORBIDDEN)
    return Response({"detail": getattr(exc, "messages", [str(exc)])},
                    status=status.HTTP_400_BAD_REQUEST)


def edit_dossier(request, dossier):
    form = DossierEditInput(data=request.data)
    form.is_valid(raise_exception=True)
    if not form.validated_data:
        return Response({"detail": "Aucun changement demandé."},
                        status=status.HTTP_400_BAD_REQUEST)
    fields = form.validated_data
    try:
        updated = update_dossier(
            actor=request.user, dossier=dossier,
            title=fields.get("title", dossier.title),
            description=fields.get("description", dossier.description),
            deadline=fields.get("deadline", dossier.deadline),
        )
    except (PermissionDenied, ValidationError) as exc:
        return _domain_error(exc)
    return Response({"kind": "dossier", "id": str(updated.pk), "updated": True})


class DossierActionsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        context = resolve_objective_context(request.query_params)
        dossier = get_object_or_404(context.filter(dossiers_for_profile(request.user)), pk=pk)
        form = DossierActionInput(data=request.data)
        form.is_valid(raise_exception=True)
        values = form.validated_data
        action = values["action"]
        actor = request.user
        try:
            if action == "link_journey":
                journey = get_object_or_404(
                    linkable_journeys_for_profile(actor, dossier=dossier),
                    pk=values["journey_id"],
                )
                link_journey(actor=actor, dossier=dossier, journey=journey)
            elif action == "unlink_journey":
                link = get_object_or_404(
                    visible_linked_journeys(actor, dossier),
                    journey_id=values["journey_id"],
                )
                unlink_journey(actor=actor, dossier=dossier, journey=link.journey)
            elif action == "add_dependency":
                links = visible_linked_journeys(actor, dossier)
                dependent = get_object_or_404(
                    links, pk=values["dependent_link_id"],
                )
                required = get_object_or_404(
                    links, pk=values["required_link_id"],
                )
                add_dependency(
                    actor=actor, dossier=dossier,
                    dependent_link=dependent, required_link=required,
                )
            elif action in ("remove_dependency", "waive_dependency"):
                dep = get_object_or_404(
                    visible_dependencies_for_profile(actor, dossier),
                    pk=values["dependency_id"],
                    state=DossierJourneyDependencyState.ACTIVE,
                )
                if action == "remove_dependency":
                    remove_dependency(actor=actor, dossier=dossier, dependency=dep)
                else:
                    waive_dependency(
                        actor=actor, dossier=dossier, dependency=dep,
                        reason=values["reason"],
                    )
            elif action == "assignment_add":
                person = get_object_or_404(
                    collaboration_candidates_for_dossier(dossier),
                    pk=values["assignee_id"],
                )
                assign_dossier(actor=actor, dossier=dossier, assignee=person)
            elif action == "assignment_remove":
                assignment = get_object_or_404(
                    active_assignments_for_dossier(dossier),
                    pk=values["assignment_id"],
                )
                unassign_dossier(actor=actor, dossier=dossier, assignment=assignment)
            elif action == "mandate_grant":
                if not can_manage_dossier_authority(actor, dossier):
                    raise PermissionDenied("Autorité requise.")
                person = get_object_or_404(
                    collaboration_candidates_for_dossier(dossier),
                    pk=values["profile_id"],
                )
                role = get_object_or_404(
                    Role.objects.filter(
                        scope_type=AuthorityScope.DOSSIER,
                        is_system=True, is_active=True,
                    ),
                    pk=values["role_id"],
                )
                grant_dossier_authority(
                    actor=actor, dossier=dossier, profile=person, role=role,
                )
            elif action == "mandate_revoke":
                mandate = get_object_or_404(
                    current_dossier_authority_mandates(dossier),
                    pk=values["mandate_id"],
                )
                revoke_dossier_authority(
                    actor=actor, dossier=dossier, mandate=mandate,
                )
            elif action == "lifecycle":
                set_dossier_lifecycle(
                    actor=actor, dossier=dossier, lifecycle=values["lifecycle"],
                )
            elif action == "project_set":
                if not can_manage_dossier(actor, dossier):
                    raise PermissionDenied("Autorité requise.")
                current = active_project_for_dossier(dossier)
                if current is not None and not can_manage_project(actor, current):
                    raise PermissionDenied("Autorité sur le Projet source requise.")
                target_id = values["project_id"]
                if target_id is None:
                    if current is not None:
                        unlink_dossier_from_project(
                            actor=actor, project=current, dossier=dossier,
                        )
                else:
                    target = get_object_or_404(
                        context.filter(projects_for_profile(actor)), pk=target_id,
                    )
                    if current is None:
                        link_dossier_to_project(
                            actor=actor, project=target, dossier=dossier,
                        )
                    elif current.pk != target.pk:
                        move_dossier_to_project(
                            actor=actor, dossier=dossier, target_project=target,
                        )
        except (PermissionDenied, ValidationError) as exc:
            return _domain_error(exc)
        return Response({
            "kind": "dossier", "id": str(dossier.pk),
            "action": action, "confirmed": True,
        })
