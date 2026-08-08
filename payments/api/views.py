from django.conf import settings
from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError

from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from payments.models import PaymentMethod, PaymentProvider
from payments.selectors import get_payment_events_visible_to, get_payments_visible_to
from payments.services import (
    cancel_payment,
    complete_manual_payment,
    complete_sandbox_payment,
    process_sandbox_webhook,
    refund_payment,
)
from payments.throttles import (
    PaymentInitiationThrottle,
    PaymentTransitionThrottle,
    PaymentWebhookThrottle,
)

from .serializers import (
    ManualCompleteSerializer,
    PaymentCreateSerializer,
    PaymentEventSerializer,
    PaymentSerializer,
    RefundRequestSerializer,
    RefundSerializer,
)


def _raise_service_error(exc):
    if isinstance(exc, DjangoPermissionDenied):
        raise PermissionDenied(str(exc)) from exc
    if isinstance(exc, DjangoValidationError):
        if hasattr(exc, "message_dict"):
            raise ValidationError(exc.message_dict) from exc
        raise ValidationError(exc.messages) from exc
    raise exc


class PaymentConfigurationAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        providers = [PaymentProvider.MANUAL]
        if getattr(settings, "PAYMENTS_SANDBOX_ENABLED", False):
            providers.insert(0, PaymentProvider.SANDBOX)
        return Response(
            {
                "providers": [
                    {"value": value, "label": label}
                    for value, label in PaymentProvider.choices
                    if value in providers
                ],
                "methods": [
                    {"value": value, "label": label}
                    for value, label in PaymentMethod.choices
                ],
                "sandbox_enabled": bool(
                    getattr(settings, "PAYMENTS_SANDBOX_ENABLED", False)
                ),
            }
        )


class PaymentViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        queryset = get_payments_visible_to(self.request.user)
        order_reference = self.request.query_params.get("order")
        payment_status = self.request.query_params.get("status")
        provider = self.request.query_params.get("provider")
        if order_reference:
            queryset = queryset.filter(order__reference=order_reference)
        if payment_status:
            queryset = queryset.filter(status=payment_status)
        if provider:
            queryset = queryset.filter(provider=provider)
        return queryset

    def get_serializer_class(self):
        if self.action == "create":
            return PaymentCreateSerializer
        return PaymentSerializer

    def get_throttles(self):
        if self.action == "create":
            return [PaymentInitiationThrottle()]
        if self.action in {
            "sandbox_complete",
            "manual_complete",
            "cancel",
            "refund",
        }:
            return [PaymentTransitionThrottle()]
        return super().get_throttles()

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            payment = serializer.save()
        except (DjangoPermissionDenied, DjangoValidationError) as exc:
            _raise_service_error(exc)
        return Response(
            PaymentSerializer(payment, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"], url_path="sandbox-complete")
    def sandbox_complete(self, request, pk=None):
        payment = self.get_object()
        try:
            complete_sandbox_payment(payment=payment, actor=request.user)
        except (DjangoPermissionDenied, DjangoValidationError) as exc:
            _raise_service_error(exc)
        payment.refresh_from_db()
        return Response(PaymentSerializer(payment, context={"request": request}).data)

    @action(detail=True, methods=["post"], url_path="manual-complete")
    def manual_complete(self, request, pk=None):
        serializer = ManualCompleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payment = self.get_object()
        try:
            complete_manual_payment(
                payment=payment,
                actor=request.user,
                provider_reference=serializer.validated_data.get(
                    "provider_reference", ""
                ),
            )
        except (DjangoPermissionDenied, DjangoValidationError) as exc:
            _raise_service_error(exc)
        payment.refresh_from_db()
        return Response(PaymentSerializer(payment, context={"request": request}).data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        payment = self.get_object()
        try:
            cancel_payment(payment=payment, actor=request.user)
        except (DjangoPermissionDenied, DjangoValidationError) as exc:
            _raise_service_error(exc)
        payment.refresh_from_db()
        return Response(PaymentSerializer(payment, context={"request": request}).data)

    @action(detail=True, methods=["post"])
    def refund(self, request, pk=None):
        serializer = RefundRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payment = self.get_object()
        try:
            refund = refund_payment(
                payment=payment,
                actor=request.user,
                reason=serializer.validated_data.get("reason", ""),
                idempotency_key=serializer.validated_data.get(
                    "idempotency_key", ""
                )
                or None,
            )
        except (DjangoPermissionDenied, DjangoValidationError) as exc:
            _raise_service_error(exc)
        return Response(
            RefundSerializer(refund, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class PaymentEventViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = PaymentEventSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = get_payment_events_visible_to(self.request.user)
        provider = self.request.query_params.get("provider")
        event_type = self.request.query_params.get("type")
        if provider:
            queryset = queryset.filter(provider=provider)
        if event_type:
            queryset = queryset.filter(event_type=event_type)
        return queryset


class SandboxWebhookAPIView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    throttle_classes = [PaymentWebhookThrottle]

    def post(self, request):
        try:
            outcome = process_sandbox_webhook(
                raw_body=request.body,
                signature=request.headers.get("X-Makolo-Signature", ""),
            )
        except DjangoPermissionDenied as exc:
            raise PermissionDenied(str(exc)) from exc
        except DjangoValidationError as exc:
            if hasattr(exc, "message_dict"):
                raise ValidationError(exc.message_dict) from exc
            raise ValidationError(exc.messages) from exc

        data = {
            "received": True,
            "duplicate": outcome.duplicate,
            "event_id": str(outcome.event.id),
            "processed": outcome.event.processed,
            "payment_reference": (
                outcome.payment.reference if outcome.payment else None
            ),
            "payment_status": outcome.payment.status if outcome.payment else None,
        }
        return Response(data, status=status.HTTP_200_OK)
