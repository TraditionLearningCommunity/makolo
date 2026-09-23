from django.core.exceptions import PermissionDenied, ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from django.urls import reverse
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from activities.models import Activity
from discovery.recommendations import build_activity_recommendations
from groups.models import Group
from trust.models import ReportCategory

from .action_stream import build_action_stream
from .bilateral_services import respond_to_action_proposal
from .models import (
    ActionProposalDirection,
    ActionProposalStatus,
    Contribution,
    ContributionKind,
)
from .profile_search import action_proposals_requiring_actor_response
from .reporting import report_contribution_to_trust
from .services import create_contribution, share_activity_to_group


def _activity_payload(activity):
    return {"id": str(activity.pk), "title": activity.title}


def _error(exc):
    detail = getattr(exc, "message_dict", None) or getattr(exc, "messages", None) or str(exc)
    return Response({"detail": detail}, status=403 if isinstance(exc, PermissionDenied) else 400)


def _proposal_response_space(proposal):
    if (
        proposal.direction == ActionProposalDirection.OWNER_TO_CANDIDATE
        and proposal.candidate_space_id
    ):
        return proposal.candidate_space
    if (
        proposal.direction == ActionProposalDirection.CANDIDATE_TO_OWNER
        and proposal.need.space_id
    ):
        return proposal.need.space
    return None


def _proposal_for_response(actor, proposal_id):
    proposal = (
        action_proposals_requiring_actor_response(actor)
        .filter(pk=proposal_id)
        .first()
    )
    if proposal is None:
        raise NotFound()
    return proposal


def _proposal_payload(proposal, *, actor, respondable=True):
    response_space = _proposal_response_space(proposal)
    acting_context = (
        {
            "kind": "space",
            "id": str(response_space.pk),
            "name": response_space.name,
            "explicit": True,
        }
        if response_space is not None
        else {
            "kind": "profile",
            "id": str(actor.pk),
            "explicit": False,
        }
    )
    links = {}
    capabilities = []
    if respondable and proposal.status == ActionProposalStatus.PENDING:
        links = {
            "self": reverse(
                "social-action-proposal-detail",
                kwargs={"proposal_id": proposal.pk},
            ),
            "respond": reverse(
                "social-action-proposal-respond",
                kwargs={"proposal_id": proposal.pk},
            ),
        }
        capabilities = ["respond"]
    return {
        "identity": {"kind": "action_proposal", "id": str(proposal.pk)},
        "state": proposal.status,
        "direction": proposal.direction,
        "need": {
            "kind": "action_need",
            "id": str(proposal.need_id),
            "title": proposal.need.title,
        },
        "acting_context": acting_context,
        "capabilities": capabilities,
        "links": links,
    }


class ActionProposalDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, proposal_id):
        proposal = _proposal_for_response(request.user, proposal_id)
        return Response(_proposal_payload(proposal, actor=request.user))


class ActionProposalRespondAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, proposal_id):
        proposal = _proposal_for_response(request.user, proposal_id)
        response_space = _proposal_response_space(proposal)
        acting_space_id = request.data.get("acting_space_id")
        if response_space is not None:
            if str(acting_space_id or "") != str(response_space.pk):
                raise ValidationError(
                    {
                        "acting_space_id": (
                            "Cette décision au nom d'un Espace exige son contexte explicite."
                        )
                    }
                )
        elif acting_space_id:
            raise ValidationError(
                {"acting_space_id": "Aucun contexte Espace n'est attendu pour cette décision."}
            )

        decision = request.data.get("status")
        if decision not in {
            ActionProposalStatus.ACCEPTED,
            ActionProposalStatus.DECLINED,
        }:
            raise ValidationError(
                {"status": "La décision doit être accepted ou declined."}
            )
        try:
            proposal = respond_to_action_proposal(
                actor=request.user,
                proposal=proposal,
                status=decision,
                response_message=request.data.get("response_message", ""),
            )
        except PermissionDenied as exc:
            raise NotFound() from exc
        except DjangoValidationError as exc:
            raise ValidationError(
                getattr(exc, "message_dict", None)
                or {"non_field_errors": getattr(exc, "messages", [str(exc)])}
            ) from exc
        return Response(
            _proposal_payload(
                proposal,
                actor=request.user,
                respondable=False,
            )
        )


class ActionStreamAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        page = build_action_stream(
            request.user,
            offset=request.query_params.get("offset", 0),
            limit=request.query_params.get("limit", 20),
        )
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
        results = build_activity_recommendations(
            request.user,
            limit=request.query_params.get("limit", 12),
        )
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
            contribution = create_contribution(
                actor=request.user,
                kind=ContributionKind.DISCUSSION,
                body=request.data.get("body", ""),
                group=group,
            )
        except (ValidationError, PermissionDenied) as exc:
            return _error(exc)
        return Response({"id": str(contribution.pk), "status": contribution.status}, status=201)


class GroupShareAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, group_id):
        group = get_object_or_404(Group, pk=group_id)
        activity = get_object_or_404(Activity, pk=request.data.get("activity_id"))
        try:
            contribution = share_activity_to_group(
                actor=request.user,
                group=group,
                activity=activity,
                body=request.data.get("body", ""),
            )
        except (ValidationError, PermissionDenied) as exc:
            return _error(exc)
        return Response({"id": str(contribution.pk), "activity_id": str(activity.pk)}, status=201)


class ReplyAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, contribution_id):
        parent = get_object_or_404(Contribution, pk=contribution_id)
        try:
            reply = create_contribution(
                actor=request.user,
                kind=ContributionKind.DISCUSSION,
                body=request.data.get("body", ""),
                parent=parent,
            )
        except (ValidationError, PermissionDenied) as exc:
            return _error(exc)
        return Response({"id": str(reply.pk), "parent_id": str(parent.pk)}, status=201)


class ContributionReportAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, contribution_id):
        contribution = get_object_or_404(
            Contribution.objects.select_related("group", "space", "activity", "occurrence"),
            pk=contribution_id,
        )
        category = request.data.get("category", ReportCategory.CONDUCT_ISSUE)
        if category not in ReportCategory.values:
            return Response({"detail": "Catégorie de signalement inconnue."}, status=400)
        try:
            report = report_contribution_to_trust(
                actor=request.user,
                contribution=contribution,
                description=request.data.get("description", ""),
                category=category,
            )
        except (ValidationError, PermissionDenied) as exc:
            return _error(exc)
        return Response({"report_id": str(report.pk), "status": report.status}, status=201)
