import uuid

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from .models import PaymentObligationProcessingMode, PaymentObligationStatus, PaymentStatus
from .obligation_forms import ObligationPaymentStartForm
from .selectors import obligations_visible_to
from .services import initiate_obligation_payment


class ObligationPaymentStartView(LoginRequiredMixin, View):
    template_name = "payments/obligation_payment_start.html"
    login_url = "core:login"

    def _obligation(self, request, obligation_pk):
        obligation = get_object_or_404(obligations_visible_to(request.user), pk=obligation_pk)
        if obligation.processing_mode != PaymentObligationProcessingMode.MAKOLO_PROVIDER:
            raise Http404("Cette obligation est réglée auprès d’un tiers.")
        if obligation.status not in {PaymentObligationStatus.PENDING, PaymentObligationStatus.PROCESSING}:
            raise Http404("Cette obligation n’est plus payable.")
        return obligation

    def get(self, request, obligation_pk):
        obligation = self._obligation(request, obligation_pk)
        active_payment = obligation.payments.filter(status__in={PaymentStatus.PENDING, PaymentStatus.PROCESSING}).order_by("-created_at").first()
        if active_payment:
            return redirect("payments:detail", pk=active_payment.pk)
        return render(request, self.template_name, {"obligation": obligation, "form": ObligationPaymentStartForm(obligation=obligation, user=request.user), "idempotency_key": uuid.uuid4().hex})

    def post(self, request, obligation_pk):
        obligation = self._obligation(request, obligation_pk)
        form = ObligationPaymentStartForm(request.POST, obligation=obligation, user=request.user)
        if form.is_valid():
            try:
                payment = initiate_obligation_payment(
                    obligation=obligation,
                    actor=request.user,
                    provider=form.cleaned_data["provider"],
                    method=form.cleaned_data["method"],
                    payer_name=form.cleaned_data.get("payer_name", ""),
                    payer_email=form.cleaned_data.get("payer_email", ""),
                    payer_phone=form.cleaned_data.get("payer_phone", ""),
                    idempotency_key=request.POST.get("idempotency_key") or None,
                )
            except (PermissionDenied, ValidationError) as exc:
                messages.error(request, "; ".join(getattr(exc, "messages", [str(exc)])))
            else:
                messages.success(request, "Paiement initialisé.")
                return redirect("payments:detail", pk=payment.pk)
        return render(request, self.template_name, {"obligation": obligation, "form": form, "idempotency_key": request.POST.get("idempotency_key") or uuid.uuid4().hex}, status=400)
