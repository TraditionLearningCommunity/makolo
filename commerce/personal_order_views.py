"""Commerce-owned personal order retrieval with no cross-beneficiary disclosures."""
from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from commerce.models import CommerceOrder


class PersonalCommerceOrderDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, order_id):
        # Buyer ownership is checked in the queryset, not after serialization.
        order = get_object_or_404(
            CommerceOrder.objects.select_related("journey__activity").filter(
                buyer=request.user,
            ),
            pk=order_id,
        )
        response = Response({
            "actor_context": {
                "kind": "profile",
                "id": str(request.user.pk),
            },
            "kind": "commerce_order",
            "id": str(order.pk),
            "title": f"Commande {order.reference}",
            "reference": order.reference,
            "status": order.status,
            "activity": {
                "kind": "activity",
                "id": str(order.journey.activity_id),
                "title": order.journey.activity.title,
            },
            "cancelled_at": order.cancelled_at.isoformat()
                if order.cancelled_at else None,
        })
        response["Cache-Control"] = "private, no-store"
        return response
