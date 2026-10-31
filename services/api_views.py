"""Native Service start API. Services owns the mutation; Discovery does not."""
from collections.abc import Mapping

from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from django.urls import reverse
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from groups.selectors import filter_queryset_by_activity_group_eligibility

from .forms import ServiceStartForm
from .models import OpportunityPolicy
from .native_start import (
    ServiceStartIdempotencyConflict,
    replay_native_start_if_exists,
    start_service_journey_idempotently,
)
from .views import public_services


def _public_service_for_viewer(*, pk, viewer):
    # Use the Web owner selector, then enforce the same Group gate as public
    # Discovery. A restricted Service cannot be started by guessing its UUID.
    queryset = filter_queryset_by_activity_group_eligibility(
        public_services(),
        viewer,
    )
    return get_object_or_404(queryset, pk=pk)


def _error_from_owner(exc):
    if hasattr(exc, "message_dict"):
        return ValidationError(exc.message_dict)
    return ValidationError(getattr(exc, "messages", [str(exc)]))


def _conflict_response():
    response = Response(
        {
            "code": "idempotency_conflict",
            "detail": "Clé déjà utilisée pour une autre demande.",
        },
        status=409,
    )
    response["Cache-Control"] = "private, no-store"
    return response


def _journey_response(*, service, journey, created):
    response = Response(
        {
            "journey": {
                "kind": "journey",
                "id": str(journey.pk),
                "workflow": journey.workflow,
                "status": journey.status,
            },
            "service": {"kind": "service", "id": str(service.pk)},
            "replayed": not created,
            "links": {
                "journey": reverse(
                    "personal-detail-projections:journey-detail",
                    kwargs={"pk": journey.pk},
                ),
            },
        },
        status=201 if created else 200,
    )
    response["Cache-Control"] = "private, no-store"
    return response


class ServiceStartAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        service = _public_service_for_viewer(pk=pk, viewer=request.user)
        opportunities = None
        if service.opportunity_policy != OpportunityPolicy.NONE:
            from opportunities.selectors import published_opportunities

            query = (request.query_params.get("q") or "").strip()[:120]
            queryset = published_opportunities()
            if query:
                queryset = queryset.filter(current_revision__title__icontains=query)
            selected = list(queryset[:31])
            opportunities = {
                "results": [
                    {
                        "kind": "opportunity",
                        "id": str(item.pk),
                        "title": item.current_revision.title,
                    }
                    for item in selected[:30]
                ],
                "has_next": len(selected) > 30,
            }
        response = Response({
            "service": {"kind": "service", "id": str(service.pk)},
            "activity": {"kind": "activity", "id": str(service.activity_id)},
            "capabilities": ["start"],
            "opportunities": opportunities,
            "requirements": {
                "opportunity_policy": service.opportunity_policy,
                "opportunity_required": (
                    service.opportunity_policy == OpportunityPolicy.REQUIRED
                ),
                "objective_max_length": 1000,
                "idempotency_key_required": True,
            },
            "links": {
                "start": reverse("services-api:start", kwargs={"pk": service.pk}),
            },
        })
        response["Cache-Control"] = "private, no-store"
        return response

    def post(self, request, pk):
        service = _public_service_for_viewer(pk=pk, viewer=request.user)
        if not isinstance(request.data, Mapping):
            raise ValidationError({"body": ["Un objet JSON est requis."]})
        unexpected = set(request.data) - {"objective", "opportunity"}
        if unexpected:
            raise ValidationError({"body": ["Champs non reconnus."]})
        operation_key = request.headers.get("Idempotency-Key", "")
        try:
            replay = replay_native_start_if_exists(
                service=service, actor=request.user, operation_key=operation_key,
                objective=request.data.get("objective") or "",
                opportunity_id=request.data.get("opportunity"),
            )
        except ServiceStartIdempotencyConflict:
            return _conflict_response()
        except DjangoValidationError as exc:
            raise _error_from_owner(exc) from exc
        if replay is not None:
            journey, created = replay
            return _journey_response(
                service=service, journey=journey, created=created,
            )

        if (
            service.opportunity_policy == OpportunityPolicy.NONE
            and request.data.get("opportunity")
        ):
            raise ValidationError({
                "opportunity": ["Ce Service n'accepte pas d'Opportunity."]
            })

        form = ServiceStartForm(data=request.data, service=service)
        if not form.is_valid():
            raise ValidationError(dict(form.errors))

        try:
            journey, created = start_service_journey_idempotently(
                service=service,
                actor=request.user,
                operation_key=operation_key,
                objective=form.cleaned_data.get("objective") or "",
                opportunity=form.cleaned_data.get("opportunity"),
            )
        except ServiceStartIdempotencyConflict:
            return _conflict_response()
        except DjangoValidationError as exc:
            raise _error_from_owner(exc) from exc

        return _journey_response(
            service=service, journey=journey, created=created,
        )
