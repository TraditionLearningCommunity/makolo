from __future__ import annotations

from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.api.projections import projection_envelope
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
        observed_at = timezone.now()
        dossier = get_object_or_404(dossiers_for_profile(request.user), pk=pk)
        readiness = resolve_dossier_readiness(dossier, viewer=request.user)

        personal_assignments = [
            {
                "kind": "assignment",
                "id": str(row.pk),
                "state": row.status,
                "assigned_at": row.assigned_at.isoformat(),
            }
            for row in active_assignments_for_dossier(dossier)
            if row.assignee_id == request.user.pk
        ]

        actor_interventions = []
        if readiness.primary_next_action is not None:
            action = readiness.primary_next_action
            actor_interventions.append(
                {
                    "state": action.reason_code or "action_required",
                    "label": action.label,
                    "journey_id": str(action.journey_id),
                    "link": (
                        f"/api/v1/me/journeys/{action.journey_id}/"
                        if action.journey_id
                        else None
                    ),
                }
            )

        data = {
            "identity": {"kind": "dossier", "id": str(dossier.pk)},
            "objective": {
                "title": dossier.title,
                "description": dossier.description or None,
            },
            "state": {"code": dossier.lifecycle},
            "deadline": _date(dossier.deadline),
            "readiness": {
                "state": readiness.status.value if readiness.status is not None else None,
                "partial": bool(readiness.is_partial),
                "hidden_signal": readiness.hidden_signal,
            },
            "visible_items": [
                {
                    "journey_id": str(item.journey_id),
                    "label": item.label,
                    "state": item.status.value,
                    "hidden_dependency": bool(item.hidden_dependency),
                    "next": (
                        {
                            "state": item.next_action.reason_code or "action_required",
                            "label": item.next_action.label,
                        }
                        if item.next_action is not None
                        else None
                    ),
                }
                for item in readiness.visible_items
            ],
            "visible_dependencies": [
                {
                    "dependent_journey_id": str(item.dependent_journey_id),
                    "dependent_label": item.dependent_label,
                    "required_journey_id": str(item.required_journey_id),
                    "required_label": item.required_label,
                    "satisfied": bool(item.is_satisfied),
                }
                for item in readiness.visible_dependencies
            ],
            "personal_responsibilities": personal_assignments,
            "actor_interventions": actor_interventions,
            "capabilities": [],
            "links": {
                "self": f"/api/v1/objectives/dossiers/{dossier.pk}/",
            },
        }
        return Response(
            projection_envelope(
                projection="objective.dossier.detail",
                data=data,
                generated_at=observed_at,
                scope="authorized",
            )
        )


class ProjectDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        observed_at = timezone.now()
        project = get_object_or_404(projects_for_profile(request.user), pk=pk)
        dossiers = visible_dossiers_for_project(request.user, project)
        data = {
            "identity": {"kind": "project", "id": str(project.pk)},
            "horizon": {
                "title": project.title,
                "description": project.description or None,
                "starts_on": _date(project.starts_on),
                "ends_on": _date(project.ends_on),
            },
            "state": {"code": project.lifecycle},
            "visible_dossiers": [
                {
                    "kind": "dossier",
                    "id": str(dossier.pk),
                    "title": dossier.title,
                    "state": dossier.lifecycle,
                    "deadline": _date(dossier.deadline),
                    "link": f"/api/v1/objectives/dossiers/{dossier.pk}/",
                }
                for dossier in dossiers
            ],
            "capabilities": [],
            "links": {
                "self": f"/api/v1/objectives/projects/{project.pk}/",
            },
        }
        return Response(
            projection_envelope(
                projection="objective.project.detail",
                data=data,
                generated_at=observed_at,
                scope="authorized",
            )
        )
