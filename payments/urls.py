from django.urls import path

from .obligation_views import ObligationPaymentStartView
from .views import (
    CommercePaymentStartView,
    ManualPaymentCompleteView,
    PaymentCancelView,
    PaymentDetailView,
    PaymentListView,
    PaymentRefundView,
    PaymentStartView,
    SandboxPaymentCompleteView,
)


app_name = "payments"

urlpatterns = [
    path("", PaymentListView.as_view(), name="list"),
    path("order/<uuid:order_pk>/new/", PaymentStartView.as_view(), name="start"),
    path("commerce-order/<uuid:order_pk>/new/", CommercePaymentStartView.as_view(), name="commerce-start"),
    path("obligation/<uuid:obligation_pk>/new/", ObligationPaymentStartView.as_view(), name="obligation-start"),
    path("<uuid:pk>/", PaymentDetailView.as_view(), name="detail"),
    path("<uuid:pk>/sandbox/complete/", SandboxPaymentCompleteView.as_view(), name="sandbox-complete"),
    path("<uuid:pk>/manual/complete/", ManualPaymentCompleteView.as_view(), name="manual-complete"),
    path("<uuid:pk>/cancel/", PaymentCancelView.as_view(), name="cancel"),
    path("<uuid:pk>/refund/", PaymentRefundView.as_view(), name="refund"),
]
