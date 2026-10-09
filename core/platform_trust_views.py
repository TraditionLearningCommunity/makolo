"""Makolo Platform presentation for Trust cases. Trust owns every transition.

Platform never reads evidence files, impersonates participants or persists a
parallel case. A human reviewer confirms a current owner-state before mutation.
"""
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.views.generic import TemplateView

from authorization.constants import PermissionCode
from authorization.services import can
from operations.services import audit_action
from trust.forms import DisputeStaffForm, ReportStaffForm, VerificationDecisionForm
from trust.models import Dispute, Report, VerificationClaim
from trust.services import (
    close_dispute, decide_dispute, decide_verification, open_dispute,
    request_dispute_information, resolve_report, revoke_verification,
    start_verification_review, triage_report,
)
from core.platform_presentation import platform_modules_for


CASE_TYPES = {
    "verification": (VerificationClaim, VerificationDecisionForm, "Vérification"),
    "report": (Report, ReportStaffForm, "Signalement"),
    "dispute": (Dispute, DisputeStaffForm, "Litige"),
}
CONSEQUENCES = {
    "verification": (
        ("review", "Placer en revue : assigne l'examen sans vérifier la demande"),
        ("verify", "Vérifier : attribue un résultat Trust, avec éventuel effet sur le Space"),
        ("reject", "Rejeter : rend cette demande non vérifiée"),
        ("revoke", "Révoquer : retire un résultat vérifié existant"),
    ),
    "report": (
        ("triage", "Trier : qualifie le signalement"),
        ("investigate", "Investiguer : ouvre l'examen du problème"),
        ("resolve", "Résoudre : enregistre une décision finale de résolution"),
        ("dismiss", "Classer : enregistre une décision finale sans suite"),
        ("dispute", "Ouvrir litige : crée, si permis, le litige rattaché au report"),
    ),
    "dispute": (
        ("request_info", "Demander information : place le litige en attente"),
        ("decide", "Décider : enregistre la décision et le remedy, sans exécuter un remboursement"),
        ("close", "Clore : clôture un litige déjà décidé"),
    ),
}


class PlatformTrustCaseView(LoginRequiredMixin, TemplateView):
    login_url = "core:login"
    template_name = "platform/trust_case.html"

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not can(request.user, PermissionCode.PLATFORM_TRUST_REVIEW):
            raise PermissionDenied("Permission Platform Trust Review requise.")
        self.case_type = kwargs["case_type"]
        if self.case_type not in CASE_TYPES:
            raise Http404
        response = super().dispatch(request, *args, **kwargs)
        response["Cache-Control"] = "private, no-store"
        return response

    def _case(self, lock=False):
        model = CASE_TYPES[self.case_type][0]
        queryset = model.objects.select_for_update() if lock else model.objects.all()
        return get_object_or_404(queryset, pk=self.kwargs["pk"])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        obj = self._case()
        model, form_type, label = CASE_TYPES[self.case_type]
        context.update(
            platform_modules=platform_modules_for(self.request.user),
            platform_page="trust",
            platform_heading=label,
            case=obj,
            case_type=self.case_type,
            case_status=obj.get_status_display(),
            version_token=obj.updated_at.isoformat(),
            consequences=CONSEQUENCES[self.case_type],
            decision_form=kwargs.get("decision_form", form_type()),
            error_message=kwargs.get("error_message", ""),
        )
        # Evidence is strictly a protected owner deep-link: no filenames,
        # file storage paths, previews or content in this projection.
        if self.case_type in ("verification", "report"):
            context["evidence_ids"] = list(obj.evidence.values_list("pk", flat=True)[:30])
        return context

    def post(self, request, *args, **kwargs):
        form_type = CASE_TYPES[self.case_type][1]
        form = form_type(request.POST)
        reason = (request.POST.get("reason") or "").strip()
        if not form.is_valid() or len(reason) < 5 or len(reason) > 2000 or request.POST.get("confirm") != "1":
            return self.render_to_response(
                self.get_context_data(decision_form=form, error_message=(
                    "Choisissez une décision, précisez un motif (5 à 2000 caractères) "
                    "et confirmez ses conséquences."
                )), status=400,
            )
        data = form.cleaned_data
        action = data["action"]
        if self.case_type == "verification" and action in {"verify", "reject", "revoke"} and not data["reason_code"]:
            return self.render_to_response(self.get_context_data(
                decision_form=form, error_message="Un code de motif Trust est obligatoire pour cette décision."
            ), status=400)
        if self.case_type == "report" and action in {"resolve", "dismiss"} and not data["resolution_code"]:
            return self.render_to_response(self.get_context_data(
                decision_form=form, error_message="Un code de résolution est obligatoire."
            ), status=400)
        if self.case_type == "dispute" and action == "decide" and (not data["decision_code"] or not data["decision_summary"]):
            return self.render_to_response(self.get_context_data(
                decision_form=form, error_message="La décision exige un code et un résumé."
            ), status=400)
        with transaction.atomic():
            current = self._case(lock=True)
            if not can(request.user, PermissionCode.PLATFORM_TRUST_REVIEW):
                raise PermissionDenied("Permission Trust révoquée.")
            if current.updated_at.isoformat() != request.POST.get("version_token"):
                return self.render_to_response(self.get_context_data(
                    decision_form=form, error_message="Ce dossier a changé. Actualisez-le avant de décider."
                ), status=409)
            before = current.status
            # Owner services are idempotent in isolation; Platform must not
            # present a repeated submission as a new audited decision.
            already_done = (
                (self.case_type == "verification" and (
                    (action == "review" and before == "under_review") or
                    (action == "verify" and before == "verified") or
                    (action == "reject" and before == "rejected") or
                    (action == "revoke" and before == "revoked")
                )) or
                (self.case_type == "report" and (
                    (action == "triage" and before == "triaged") or
                    (action == "investigate" and before == "investigating") or
                    (action == "resolve" and before == "resolved") or
                    (action == "dismiss" and before == "dismissed") or
                    (action == "dispute" and Dispute.objects.filter(report=current).exists())
                )) or
                (self.case_type == "dispute" and (
                    (action == "request_info" and before == "awaiting_information") or
                    (action == "decide" and before == "decided") or
                    (action == "close" and before == "closed")
                ))
            )
            if already_done:
                return self.render_to_response(self.get_context_data(
                    decision_form=form, error_message="Cette action a déjà été appliquée. Aucune nouvelle décision n'a été enregistrée."
                ), status=409)
            try:
                outcome = self._apply(current, action, data, request.user)
            except ValidationError as exc:
                detail = exc.message_dict if hasattr(exc, "message_dict") else exc.messages
                return self.render_to_response(self.get_context_data(
                    decision_form=form, error_message=str(detail)
                ), status=409)
            current.refresh_from_db()
            audit_action(
                actor=request.user,
                action=f"platform.trust.{self.case_type}.{action}",
                target_type=f"trust_{self.case_type}", target_id=current.pk,
                summary=f"Décision Trust {action} sur {self.case_type}",
                before={"status": before},
                after={"status": current.status, "related_id": str(outcome.pk) if outcome.pk != current.pk else None},
                metadata={"reason": reason},
            )
        messages.success(request, f"Décision Trust appliquée : {before} vers {current.status}. Motif enregistré.")
        return redirect(request.path)

    def _apply(self, obj, action, data, actor):
        if self.case_type == "verification":
            if action == "review":
                return start_verification_review(claim=obj, actor=actor)
            if action in {"verify", "reject"}:
                return decide_verification(
                    claim=obj, actor=actor, verified=action == "verify",
                    reason_code=data["reason_code"], private_note=data["private_note"],
                    valid_until=data["valid_until"] if action == "verify" else None,
                )
            return revoke_verification(
                claim=obj, actor=actor, reason_code=data["reason_code"],
                private_note=data["private_note"],
            )
        if self.case_type == "report":
            if action in {"triage", "investigate"}:
                return triage_report(
                    report=obj, actor=actor, investigate=action == "investigate",
                    private_note=data["private_note"],
                )
            if action in {"resolve", "dismiss"}:
                return resolve_report(
                    report=obj, actor=actor, resolution_code=data["resolution_code"],
                    dismissed=action == "dismiss", private_note=data["private_note"],
                )
            return open_dispute(report=obj, actor=actor)
        if action == "request_info":
            return request_dispute_information(dispute=obj, actor=actor)
        if action == "decide":
            return decide_dispute(
                dispute=obj, actor=actor, decision_code=data["decision_code"],
                decision_summary=data["decision_summary"],
                remedy_code=data["remedy_code"] or "no_action",
                private_note=data["private_note"],
            )
        return close_dispute(dispute=obj, actor=actor)
