from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.http import Http404
from django.shortcuts import redirect, render
from django.views import View

from journeys.collaboration_services import create_artifact, create_artifact_version
from payments.models import PaymentObligationProcessingMode, PaymentObligationStatus
from payments.selectors import obligations_visible_to

from .participant_forms import ExternalPaymentEvidenceForm, ParticipantArtifactUploadForm, ParticipantArtifactVersionForm
from .participant_services import submit_external_payment_evidence_with_receipt
from .selectors import service_artifacts_visible_to, service_journeys_visible_to


class _ParticipantServiceJourneyMixin(LoginRequiredMixin):
    login_url = "core:login"

    def participant_journey(self, request, pk):
        journey = service_journeys_visible_to(request.user).filter(pk=pk, beneficiary=request.user).first()
        if journey is None:
            raise Http404
        return journey


class ParticipantArtifactUploadView(_ParticipantServiceJourneyMixin, View):
    template_name = "services/participant_artifact_upload.html"

    def get(self, request, pk):
        journey = self.participant_journey(request, pk)
        return render(request, self.template_name, {"journey": journey, "form": ParticipantArtifactUploadForm(journey=journey)})

    def post(self, request, pk):
        journey = self.participant_journey(request, pk)
        form = ParticipantArtifactUploadForm(request.POST, request.FILES, journey=journey)
        if form.is_valid():
            try:
                create_artifact(
                    journey=journey,
                    step=form.cleaned_data.get("step"),
                    uploaded_file=form.cleaned_data["file"],
                    uploaded_by=request.user,
                    kind=form.cleaned_data["kind"],
                    title=form.cleaned_data["title"],
                )
            except ValidationError as exc:
                form.add_error("file", "; ".join(getattr(exc, "messages", [str(exc)])))
            else:
                messages.success(request, "Document ajouté à votre démarche.")
                return redirect("core:participant-journey-detail", pk=journey.pk)
        return render(request, self.template_name, {"journey": journey, "form": form}, status=400)


class ParticipantArtifactVersionView(LoginRequiredMixin, View):
    template_name = "services/participant_artifact_version.html"
    login_url = "core:login"

    def _artifact(self, request, artifact_pk):
        journey = service_journeys_visible_to(request.user).filter(beneficiary=request.user, artifacts__pk=artifact_pk).first()
        if journey is None:
            raise Http404
        artifact = service_artifacts_visible_to(request.user, journey=journey).filter(pk=artifact_pk).first()
        if artifact is None:
            raise Http404
        return journey, artifact

    def get(self, request, artifact_pk):
        journey, artifact = self._artifact(request, artifact_pk)
        return render(request, self.template_name, {"journey": journey, "artifact": artifact, "form": ParticipantArtifactVersionForm()})

    def post(self, request, artifact_pk):
        journey, artifact = self._artifact(request, artifact_pk)
        form = ParticipantArtifactVersionForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                create_artifact_version(artifact=artifact, uploaded_file=form.cleaned_data["file"], uploaded_by=request.user)
            except ValidationError as exc:
                form.add_error("file", "; ".join(getattr(exc, "messages", [str(exc)])))
            else:
                messages.success(request, "Une nouvelle version du document a été créée. L’historique précédent est conservé.")
                return redirect("core:participant-journey-detail", pk=journey.pk)
        return render(request, self.template_name, {"journey": journey, "artifact": artifact, "form": form}, status=400)


class ParticipantExternalPaymentEvidenceView(_ParticipantServiceJourneyMixin, View):
    template_name = "services/participant_payment_evidence.html"

    def _obligation(self, request, journey, obligation_pk):
        obligation = obligations_visible_to(request.user).filter(pk=obligation_pk, journey=journey).first()
        if obligation is None or obligation.processing_mode != PaymentObligationProcessingMode.EXTERNAL:
            raise Http404
        if obligation.status in {
            PaymentObligationStatus.SATISFIED,
            PaymentObligationStatus.WAIVED,
            PaymentObligationStatus.EXPIRED,
            PaymentObligationStatus.CANCELLED,
            PaymentObligationStatus.REFUNDED,
        }:
            raise Http404
        return obligation

    def get(self, request, pk, obligation_pk):
        journey = self.participant_journey(request, pk)
        obligation = self._obligation(request, journey, obligation_pk)
        return render(request, self.template_name, {"journey": journey, "obligation": obligation, "form": ExternalPaymentEvidenceForm()})

    def post(self, request, pk, obligation_pk):
        journey = self.participant_journey(request, pk)
        obligation = self._obligation(request, journey, obligation_pk)
        form = ExternalPaymentEvidenceForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                submit_external_payment_evidence_with_receipt(
                    journey=journey,
                    obligation=obligation,
                    actor=request.user,
                    uploaded_file=form.cleaned_data["file"],
                    paid_at=form.cleaned_data["paid_at"],
                    external_reference=form.cleaned_data.get("external_reference", ""),
                )
            except ValidationError as exc:
                form.add_error(None, "; ".join(getattr(exc, "messages", [str(exc)])))
            else:
                messages.success(request, "Votre preuve de paiement a été envoyée pour vérification.")
                return redirect("core:participant-journey-detail", pk=journey.pk)
        return render(request, self.template_name, {"journey": journey, "obligation": obligation, "form": form}, status=400)
