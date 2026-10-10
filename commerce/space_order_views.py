"""Commerce-owned, read-only order retrieval for the active Space actor.

No payment, buyer PII or secrets appear in this projection.
"""
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from authorization.constants import PermissionCode
from authorization.selectors import has_direct_space_permission
from commerce.models import CommerceOrder
from organizations.api.space_history_projection import visible_history_activity_ids
from organizations.api.workspace_projection import workspace_spaces


class SpaceCommerceOrderDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, slug, order_id):
        space = workspace_spaces(request.user).filter(slug=slug).first()
        if space is None or not has_direct_space_permission(
            request.user, space, PermissionCode.ORDERS_VIEW
        ):
            raise NotFound()

        responsibility = (request.query_params.get("responsibility") or "all").strip()
        activity_ids = visible_history_activity_ids(
            profile=request.user, space=space,
            responsibility_key=responsibility,
        )
        if activity_ids is None:
            raise NotFound()
        order = get_object_or_404(
            CommerceOrder.objects.select_related("journey__activity").filter(
                payee_space=space,
                journey__activity_id__in=activity_ids,
            ),
            pk=order_id,
        )
        response = Response({
            "actor_context": {
                "kind": "space", "id": str(space.pk), "name": space.name,
            },
            "kind": "commerce_order",
            "id": str(order.pk),
            "reference": order.reference,
            "title": f"Commande {order.reference}",
            "status": order.status,
            "cancelled_at": order.cancelled_at.isoformat()
                if order.cancelled_at else None,
            "activity": {
                "id": str(order.journey.activity_id),
                "title": order.journey.activity.title,
            },
            "coverage": {"state": "owner_backed", "owner": "commerce"},
        })
        response["Cache-Control"] = "private, no-store"
        return response
