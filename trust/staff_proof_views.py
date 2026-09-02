from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect
from django.views.generic import TemplateView, View

from authorization.constants import PermissionCode
from authorization.services import can

from .models import Proof
from .services import revoke_proof


def _require_reviewer(user):
    if not user.is_authenticated or not can(user, PermissionCode.PLATFORM_TRUST_REVIEW):
        raise PermissionDenied("Autorité Trust plateforme requise.")


class StaffProofQueueView(LoginRequiredMixin, TemplateView):
    template_name = "trust/staff_proof_queue.html"
    login_url = "core:login"

    def get_context_data(self, **kwargs):
        _require_reviewer(self.request.user)
        context = super().get_context_data(**kwargs)
        context["proofs"] = Proof.objects.select_related(
            "subject_profile", "journey__activity", "occurrence"
        ).order_by("-issued_at")[:100]
        return context


class StaffProofRevokeView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, proof_id):
        _require_reviewer(request.user)
        proof = get_object_or_404(Proof, pk=proof_id)
        reason = (request.POST.get("reason") or "").strip()
        if not reason:
            messages.error(request, "Une raison de révocation est requise.")
            return redirect("trust:staff-proof-queue")
        try:
            revoke_proof(proof=proof, actor=request.user, reason=reason)
        except (ValidationError, PermissionDenied) as exc:
            messages.error(request, "; ".join(getattr(exc, "messages", [str(exc)])))
        else:
            messages.success(request, "Attestation révoquée ; son historique reste vérifiable.")
        return redirect("trust:staff-proof-queue")
