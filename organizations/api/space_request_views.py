"""Minimal owner-depth bridge for a Space's existing JourneyRequest decisions.

Now only links here. JourneyRequest and its transactional services remain the
sole owners of status and mutation. No confidential applicant data is mirrored.
"""
from __future__ import annotations

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from authorization.constants import PermissionCode
from authorization.selectors import activity_ids_with_direct_permission
from journeys.models import JourneyRequest, JourneyStatus, RequestStatus
from journeys.services import approve_request, reject_request

from .space_work_projection import (
    _activity_scope_from_responsibility,
    _visible_activity_ids,
)
from .workspace_projection import workspace_spaces


class SpaceJourneyRequestAPIView(APIView):
    """Fresh owner read / one-shot decision, scoped by viewer and Space.

    A displayed Now handoff conveys neither authorization nor a mutation.
    """

    permission_classes = [IsAuthenticated]

    @staticmethod
    def _response(payload, status=200):
        response = Response(payload, status=status)
        response["Cache-Control"] = "private, no-store"
        return response

    def _owner(self, request, slug, request_id):
        space = workspace_spaces(request.user).filter(slug=slug).first()
        if space is None:
            raise NotFound()
        responsibility = (
            request.query_params.get("responsibility") or "all"
        ).strip() or "all"
        lens = _activity_scope_from_responsibility(
            request.user, space, responsibility
        )
        if lens == set():
            raise NotFound()
        allowed = _visible_activity_ids(request.user, space)
        allowed &= set(activity_ids_with_direct_permission(
            request.user, PermissionCode.ACTIVITY_REQUESTS_VIEW
        ))
        if lens is not None:
            allowed &= lens
        if not allowed:
            raise NotFound()
        owner = (
            JourneyRequest.objects.filter(
                pk=request_id, journey__activity_id__in=allowed,
                journey__activity__space=space,
            )
            .select_related("journey__activity")
            .first()
        )
        if owner is None:
            raise NotFound()
        return space, responsibility, owner

    def _projection(self, request, space, responsibility, owner):
        activity = owner.journey.activity
        authorized_to_decide = activity.pk in set(
            activity_ids_with_direct_permission(
                request.user, PermissionCode.ACTIVITY_REQUESTS_DECIDE
            )
        )
        can_decide = (
            authorized_to_decide
            and owner.status == RequestStatus.PENDING
            and owner.journey.status in {
                JourneyStatus.SUBMITTED, JourneyStatus.PENDING_APPROVAL,
            }
            and (owner.expires_at is None or owner.expires_at > timezone.now())
        )
        return {
            "space": {"id": str(space.pk), "slug": space.slug, "name": space.name},
            "responsibility": responsibility,
            "request": {
                "id": str(owner.pk),
                "status": owner.status,
                "purpose": owner.purpose,
                "submitted_at": owner.submitted_at.isoformat(),
                "expires_at": owner.expires_at.isoformat() if owner.expires_at else None,
                "activity": {"id": str(activity.pk), "title": activity.title},
            },
            "capabilities": {
                "decide": can_decide,
            },
        }

    def get(self, request, slug, request_id):
        space, responsibility, owner = self._owner(request, slug, request_id)
        return self._response(self._projection(request, space, responsibility, owner))

    def post(self, request, slug, request_id):
        space, responsibility, owner = self._owner(request, slug, request_id)
        decision = request.data.get("decision") if isinstance(request.data, dict) else None
        if decision not in {"approve", "reject"}:
            raise ValidationError({"decision": "Décision inconnue."})
        if not self._projection(request, space, responsibility, owner)["capabilities"]["decide"]:
            # No optimistic success, including when a previous command already won.
            return self._response({"detail": "Décision indisponible dans le contexte actuel."}, status=409)
        try:
            if decision == "approve":
                approve_request(request=owner, actor=request.user)
            else:
                reject_request(request=owner, actor=request.user)
        except (DjangoValidationError, DjangoPermissionDenied) as error:
            # Includes owner-side TOCTOU, expiry, concurrency and revoked rights.
            message = "; ".join(error.messages) if hasattr(error, "messages") else str(error)
            return self._response({"detail": message}, status=409)
        owner.refresh_from_db()
        result = self._projection(request, space, responsibility, owner)
        result["confirmed_by_owner"] = True
        return self._response(result)
