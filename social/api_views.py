from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from activities.models import Activity
from discovery.recommendations import build_activity_recommendations
from groups.models import Group

from .action_stream import build_action_stream
from .models import Contribution, ContributionKind
from .services import create_contribution, share_activity_to_group


def _activity_payload(activity):
    return {"id": str(activity.pk), "title": activity.title}


def _error(exc):
    detail = getattr(exc, "message_dict", None) or getattr(exc, "messages", None) or str(exc)
    return Response({"detail": detail}, status=403 if isinstance(exc, PermissionDenied) else 400)


class ActionStreamAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        page = build_action_stream(request.user, offset=request.query_params.get("offset", 0), limit=request.query_params.get("limit", 20))
        return Response({
            "items": [{
                "key": item.key,
                "kind": item.kind,
                "title": item.title,
                "summary": item.summary,
                "activity": _activity_payload(item.activity) if item.activity else None,
                "reasons": list(item.reasons),
                "cta": {"label": item.cta_label, "url": item.cta_url} if item.cta_url else None,
            } for item in page.items],
            "offset": page.offset,
            "limit": page.limit,
            "has_more": page.has_more,
        })


class RecommendationsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        results = build_activity_recommendations(request.user, limit=request.query_params.get("limit", 12))
        return Response({"results": [{
            "activity": _activity_payload(item.activity),
            "vertical": item.vertical,
            "reasons": [{"code": reason.code, "label": reason.label} for reason in item.reasons],
            "cta": {"label": item.cta_label, "url": item.cta_url},
        } for item in results]})


class GroupContributionAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, group_id):
        group = get_object_or_404(Group, pk=group_id)
        try:
            contribution = create_contribution(actor=request.user, kind=ContributionKind.DISCUSSION, body=request.data.get("body", ""), group=group)
        except (ValidationError, PermissionDenied) as exc:
            return _error(exc)
        return Response({"id": str(contribution.pk), "status": contribution.status}, status=201)


class GroupShareAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, group_id):
        group = get_object_or_404(Group, pk=group_id)
        activity = get_object_or_404(Activity, pk=request.data.get("activity_id"))
        try:
            contribution = share_activity_to_group(actor=request.user, group=group, activity=activity, body=request.data.get("body", ""))
        except (ValidationError, PermissionDenied) as exc:
            return _error(exc)
        return Response({"id": str(contribution.pk), "activity_id": str(activity.pk)}, status=201)


class ReplyAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, contribution_id):
        parent = get_object_or_404(Contribution, pk=contribution_id)
        try:
            reply = create_contribution(actor=request.user, kind=ContributionKind.DISCUSSION, body=request.data.get("body", ""), parent=parent)
        except (ValidationError, PermissionDenied) as exc:
            return _error(exc)
        return Response({"id": str(reply.pk), "parent_id": str(parent.pk)}, status=201)
