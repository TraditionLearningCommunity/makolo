from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import TemplateView

from authorization.constants import PermissionCode
from authorization.services import can
from journeys.models import Journey
from organizations.models import Organization

from .forms import DisputeStaffForm, FeedbackForm, ReportForm, ReportStaffForm, VerificationDecisionForm, VerificationRequestForm
from .models import Dispute, Feedback, Proof, Report, TrustEvidence, VerificationClaim, VerificationClaimType
from .selectors import (
    dispute_visible_to,
    get_operator_trust_summary,
    get_public_trust_summary,
    proofs_for_profile,
    public_proof_by_id,
    report_visible_to,
)
from .services import (
    attach_trust_evidence,
    can_access_evidence,
    can_manage_space_trust,
    close_dispute,
    create_report,
    decide_dispute,
    decide_verification,
    open_dispute,
    request_dispute_information,
    request_verification,
    resolve_report,
    revoke_verification,
    start_verification_review,
    submit_feedback,
    triage_report,
)


def _error_text(exc):
    if hasattr(exc, "message_dict"):
        return "; ".join(str(value) for values in exc.message_dict.values() for value in values)
    return "; ".join(getattr(exc, "messages", [str(exc)]))


def _require_platform(request):
    if not request.user.is_authenticated or not can(request.user, PermissionCode.PLATFORM_TRUST_REVIEW):
        raise PermissionDenied("Autorité Trust plateforme requise.")


class PublicSpaceTrustView(TemplateView):
    template_name = "trust/public_space_summary.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        space = get_object_or_404(Organization, slug=kwargs["slug"], public_profile=True)
        context["space"] = space
        context["trust_summary"] = get_public_trust_summary(space, viewer=self.request.user)
        return context


class SpaceTrustConsoleView(LoginRequiredMixin, TemplateView):
    template_name = "trust/space_console.html"
    login_url = "core:login"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        space = get_object_or_404(Organization, slug=kwargs["slug"])
        context["space"] = space
        context["trust_summary"] = get_operator_trust_summary(space, self.request.user)
        context["claims"] = VerificationClaim.objects.filter(subject_space=space).order_by("-requested_at")[:50]
        context["can_manage_trust"] = can_manage_space_trust(self.request.user, space)
        return context


class SpaceVerificationRequestView(LoginRequiredMixin, View):
    login_url = "core:login"
    template_name = "trust/verification_request.html"

    def _space(self, slug):
        return get_object_or_404(Organization, slug=slug)

    def get(self, request, slug):
        space = self._space(slug)
        if not can_manage_space_trust(request.user, space):
            raise PermissionDenied("Mandate Trust requis.")
        return render(request, self.template_name, {"space": space, "form": VerificationRequestForm(initial={"claim_type": VerificationClaimType.ORGANIZATION_IDENTITY})})

    def post(self, request, slug):
        space = self._space(slug)
        form = VerificationRequestForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                claim = request_verification(actor=request.user, subject_space=space, claim_type=form.cleaned_data["claim_type"])
                if form.cleaned_data.get("evidence"):
                    attach_trust_evidence(actor=request.user, uploaded_file=form.cleaned_data["evidence"], verification_claim=claim)
            except (ValidationError, PermissionDenied) as exc:
                form.add_error(None, _error_text(exc))
            else:
                messages.success(request, "Demande de vérification enregistrée.")
                return redirect("trust:space-console", slug=space.slug)
        return render(request, self.template_name, {"space": space, "form": form}, status=400)


class JourneyFeedbackView(LoginRequiredMixin, View):
    login_url = "core:login"
    template_name = "trust/feedback_form.html"

    def _journey(self, request, journey_id):
        return get_object_or_404(Journey.objects.select_related("activity", "occurrence"), pk=journey_id, beneficiary=request.user)

    def get(self, request, journey_id):
        journey = self._journey(request, journey_id)
        return render(request, self.template_name, {"journey": journey, "form": FeedbackForm()})

    def post(self, request, journey_id):
        journey = self._journey(request, journey_id)
        form = FeedbackForm(request.POST)
        if form.is_valid():
            try:
                submit_feedback(journey=journey, actor=request.user, **form.cleaned_data)
            except (ValidationError, PermissionDenied) as exc:
                form.add_error(None, _error_text(exc))
            else:
                messages.success(request, "Votre retour d’expérience vérifiée a été enregistré.")
                return redirect("core:participant-history")
        return render(request, self.template_name, {"journey": journey, "form": form}, status=400)


class JourneyReportView(LoginRequiredMixin, View):
    login_url = "core:login"
    template_name = "trust/report_form.html"

    def _journey(self, request, journey_id):
        return get_object_or_404(Journey.objects.select_related("activity", "occurrence", "activity__space"), pk=journey_id, beneficiary=request.user)

    def get(self, request, journey_id):
        journey = self._journey(request, journey_id)
        return render(request, self.template_name, {"journey": journey, "form": ReportForm()})

    def post(self, request, journey_id):
        journey = self._journey(request, journey_id)
        form = ReportForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                report = create_report(actor=request.user, journey=journey, category=form.cleaned_data["category"], description=form.cleaned_data["description"])
                if form.cleaned_data.get("evidence"):
                    attach_trust_evidence(actor=request.user, uploaded_file=form.cleaned_data["evidence"], report=report)
            except (ValidationError, PermissionDenied) as exc:
                form.add_error(None, _error_text(exc))
            else:
                messages.success(request, "Votre signalement a été transmis à Makolo.")
                return redirect("trust:report-detail", report_id=report.pk)
        return render(request, self.template_name, {"journey": journey, "form": form}, status=400)


class ReportDetailView(LoginRequiredMixin, TemplateView):
    template_name = "trust/report_detail.html"
    login_url = "core:login"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        report = get_object_or_404(Report.objects.select_related("journey__activity", "space", "reporter"), pk=kwargs["report_id"])
        if not report_visible_to(report, self.request.user):
            raise PermissionDenied("Accès au signalement refusé.")
        context["report"] = report
        return context


class DisputeDetailView(LoginRequiredMixin, TemplateView):
    template_name = "trust/dispute_detail.html"
    login_url = "core:login"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        dispute = get_object_or_404(Dispute.objects.select_related("report", "journey__activity", "respondent_space", "claimant"), pk=kwargs["dispute_id"])
        if not dispute_visible_to(dispute, self.request.user):
            raise PermissionDenied("Accès au litige refusé.")
        context["dispute"] = dispute
        return context


class EvidenceDownloadView(LoginRequiredMixin, View):
    login_url = "core:login"

    def get(self, request, evidence_id):
        evidence = get_object_or_404(TrustEvidence.objects.select_related("verification_claim__subject_space", "report"), pk=evidence_id)
        if not can_access_evidence(evidence=evidence, actor=request.user):
            raise PermissionDenied("Accès à l’evidence refusé.")
        try:
            handle = evidence.file.open("rb")
        except FileNotFoundError as exc:
            raise Http404 from exc
        return FileResponse(handle, as_attachment=True, filename="makolo-trust-evidence")


class MyProofsView(LoginRequiredMixin, TemplateView):
    template_name = "trust/my_proofs.html"
    login_url = "core:login"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["proofs"] = proofs_for_profile(self.request.user)
        return context


class PublicProofVerifyView(TemplateView):
    template_name = "trust/proof_verify.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        proof = public_proof_by_id(kwargs["public_id"])
        if proof is None:
            raise Http404
        context["proof"] = proof
        return context


class StaffTrustQueueView(LoginRequiredMixin, TemplateView):
    template_name = "trust/staff_queue.html"
    login_url = "core:login"

    def get_context_data(self, **kwargs):
        _require_platform(self.request)
        context = super().get_context_data(**kwargs)
        context["verification_queue"] = VerificationClaim.objects.filter(status__in=["requested", "under_review"]).select_related("subject_profile", "subject_space", "requested_by")[:100]
        context["report_queue"] = Report.objects.filter(status__in=["open", "triaged", "investigating"]).select_related("reporter", "space", "journey")[:100]
        context["dispute_queue"] = Dispute.objects.exclude(status="closed").select_related("claimant", "respondent_space", "respondent_profile")[:100]
        return context


class StaffVerificationActionView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, claim_id):
        _require_platform(request)
        claim = get_object_or_404(VerificationClaim, pk=claim_id)
        form = VerificationDecisionForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Action de vérification invalide.")
            return redirect("trust:staff-queue")
        data = form.cleaned_data
        try:
            if data["action"] == "review":
                start_verification_review(claim=claim, actor=request.user)
            elif data["action"] == "verify":
                decide_verification(claim=claim, actor=request.user, verified=True, reason_code=data["reason_code"], private_note=data["private_note"], valid_until=data["valid_until"])
            elif data["action"] == "reject":
                decide_verification(claim=claim, actor=request.user, verified=False, reason_code=data["reason_code"], private_note=data["private_note"])
            else:
                revoke_verification(claim=claim, actor=request.user, reason_code=data["reason_code"], private_note=data["private_note"])
        except (ValidationError, PermissionDenied) as exc:
            messages.error(request, _error_text(exc))
        else:
            messages.success(request, "Vérification mise à jour.")
        return redirect("trust:staff-queue")


class StaffReportActionView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, report_id):
        _require_platform(request)
        report = get_object_or_404(Report, pk=report_id)
        form = ReportStaffForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Action de signalement invalide.")
            return redirect("trust:staff-queue")
        data = form.cleaned_data
        try:
            if data["action"] in {"triage", "investigate"}:
                triage_report(report=report, actor=request.user, investigate=data["action"] == "investigate", private_note=data["private_note"])
            elif data["action"] == "resolve":
                resolve_report(report=report, actor=request.user, resolution_code=data["resolution_code"], private_note=data["private_note"])
            elif data["action"] == "dismiss":
                resolve_report(report=report, actor=request.user, resolution_code=data["resolution_code"], dismissed=True, private_note=data["private_note"])
            else:
                open_dispute(report=report, actor=request.user)
        except (ValidationError, PermissionDenied) as exc:
            messages.error(request, _error_text(exc))
        else:
            messages.success(request, "Signalement mis à jour.")
        return redirect("trust:staff-queue")


class StaffDisputeActionView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, dispute_id):
        _require_platform(request)
        dispute = get_object_or_404(Dispute, pk=dispute_id)
        form = DisputeStaffForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Action de litige invalide.")
            return redirect("trust:staff-queue")
        data = form.cleaned_data
        try:
            if data["action"] == "request_info":
                request_dispute_information(dispute=dispute, actor=request.user)
            elif data["action"] == "decide":
                decide_dispute(dispute=dispute, actor=request.user, decision_code=data["decision_code"], decision_summary=data["decision_summary"], remedy_code=data["remedy_code"] or "no_action", private_note=data["private_note"])
            else:
                close_dispute(dispute=dispute, actor=request.user)
        except (ValidationError, PermissionDenied) as exc:
            messages.error(request, _error_text(exc))
        else:
            messages.success(request, "Litige mis à jour.")
        return redirect("trust:staff-queue")
