"""Owner-backed Space reads for institution-payable PaymentObligations.

The Payment domain keeps the obligation, payer, money and status. Space Now
only signals that a due, still-unpaid obligation deserves attention.
"""
from __future__ import annotations

from django.http import Http404
from django.shortcuts import get_object_or_404
from django.views.generic import TemplateView
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from authorization.constants import PermissionCode
from authorization.selectors import has_direct_space_permission
from organizations.api.space_work_projection import (
    _activity_scope_from_responsibility,
    _visible_activity_ids,
)
from organizations.api.workspace_projection import workspace_spaces
from organizations.space_web_views import SpaceWebMixin

from .models import PaymentObligation


def space_payer_obligation(*, profile, space, obligation_id, responsibility):
    """Resolve the canonical payer's obligation and exact viewer scope."""
    if not has_direct_space_permission(profile, space, PermissionCode.FINANCE_VIEW):
        return None
    lens = _activity_scope_from_responsibility(profile, space, responsibility)
    if lens == set():
        return None
    visible = _visible_activity_ids(profile, space)
    if lens is not None:
        visible &= lens
    return (
        PaymentObligation.objects.filter(
            pk=obligation_id,
            payer_space=space,
            commerce_order__isnull=True,
            journey__activity__space=space,
            journey__activity_id__in=visible,
        )
        .select_related("journey__activity")
        .first()
    )


def _payload(space, obligation, responsibility):
    return {
        "space": {"id": str(space.pk), "slug": space.slug, "name": space.name},
        "responsibility": responsibility,
        "kind": "payment_obligation",
        "id": str(obligation.pk),
        "label": obligation.label,
        "status": obligation.status,
        "amount": format(obligation.amount, ".2f"),
        "currency": obligation.currency,
        "due_at": obligation.due_at.isoformat() if obligation.due_at else None,
        "processing_mode": obligation.processing_mode,
        "activity": {
            "id": str(obligation.journey.activity_id),
            "title": obligation.journey.activity.title,
        },
        "owner": "payments",
        "mutation": "not_supported_by_this_read",
    }


class SpacePayerObligationAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, slug, obligation_id):
        space = workspace_spaces(request.user).filter(slug=slug).first()
        if space is None:
            raise NotFound()
        responsibility = (
            request.query_params.get("responsibility") or "all"
        ).strip() or "all"
        obligation = space_payer_obligation(
            profile=request.user, space=space,
            obligation_id=obligation_id, responsibility=responsibility,
        )
        if obligation is None:
            raise NotFound()
        response = Response(_payload(space, obligation, responsibility))
        response["Cache-Control"] = "private, no-store"
        return response


class SpacePayerObligationWebView(SpaceWebMixin, TemplateView):
    template_name = "payments/space_payer_obligation.html"
    space_page_title = "Obligation financière"
    space_nav_key = ""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        responsibility = self.selected_responsibility["key"]
        obligation = space_payer_obligation(
            profile=self.request.user, space=self.space,
            obligation_id=self.kwargs["obligation_id"],
            responsibility=responsibility,
        )
        if obligation is None:
            raise Http404
        context["obligation"] = obligation
        context["payment_facts"] = _payload(self.space, obligation, responsibility)
        return context
