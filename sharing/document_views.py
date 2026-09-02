from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404
from django.shortcuts import redirect, render
from django.views import View

from journeys.collaboration_models import JourneyArtifactKind, JourneyArtifactSensitivity, JourneyStep
from journeys.models import Journey

from .document_services import (
    absorb_capture_into_journey,
    capture_for_actor,
    create_inbound_capture,
    discard_capture,
)
from .inbound_models import InboundCaptureSourceKind


class InboundCaptureCreateView(LoginRequiredMixin, View):
    template_name = "sharing/inbound_create.html"

    def get(self, request):
        return render(request, self.template_name, {"source_kinds": InboundCaptureSourceKind.choices})

    def post(self, request):
        try:
            capture = create_inbound_capture(
                actor=request.user,
                source_kind=request.POST.get("source_kind", ""),
                source_url=request.POST.get("source_url", ""),
                text=request.POST.get("text", ""),
                uploaded_file=request.FILES.get("file"),
            )
        except ValidationError as exc:
            return render(
                request,
                self.template_name,
                {"source_kinds": InboundCaptureSourceKind.choices, "errors": exc.messages},
                status=400,
            )
        target = redirect("sharing:inbound-detail", capture_id=capture.pk)
        journey_id = request.GET.get("journey") or request.POST.get("journey")
        if journey_id:
            target["Location"] += f"?journey={journey_id}"
        return target


class InboundCaptureDetailView(LoginRequiredMixin, View):
    template_name = "sharing/inbound_detail.html"

    def get(self, request, capture_id):
        try:
            capture = capture_for_actor(actor=request.user, capture_id=capture_id)
        except PermissionDenied as exc:
            raise Http404 from exc
        journeys = Journey.objects.filter(beneficiary=request.user).select_related("activity").order_by("-created_at")
        steps = JourneyStep.objects.filter(journey__beneficiary=request.user).select_related("journey").order_by(
            "journey_id", "position", "created_at"
        )
        return render(
            request,
            self.template_name,
            {
                "capture": capture,
                "journeys": journeys,
                "steps": steps,
                "artifact_kinds": JourneyArtifactKind.choices,
                "sensitivities": JourneyArtifactSensitivity.choices,
                "selected_journey": request.GET.get("journey", ""),
            },
        )


class InboundCaptureAbsorbView(LoginRequiredMixin, View):
    def post(self, request, capture_id):
        try:
            absorb_capture_into_journey(
                actor=request.user,
                capture_id=capture_id,
                journey_id=request.POST.get("journey_id"),
                step_id=request.POST.get("step_id") or None,
                kind=request.POST.get("kind") or JourneyArtifactKind.OTHER,
                sensitivity=request.POST.get("sensitivity") or JourneyArtifactSensitivity.SENSITIVE,
                title=request.POST.get("title", ""),
            )
        except PermissionDenied as exc:
            raise Http404 from exc
        except (ValidationError, ValueError) as exc:
            messages.error(request, "; ".join(getattr(exc, "messages", [str(exc)])))
            return redirect("sharing:inbound-detail", capture_id=capture_id)
        messages.success(request, "L’élément a été ajouté à votre démarche.")
        return redirect("sharing:inbound-detail", capture_id=capture_id)


class InboundCaptureDiscardView(LoginRequiredMixin, View):
    def post(self, request, capture_id):
        try:
            discard_capture(actor=request.user, capture_id=capture_id)
        except PermissionDenied as exc:
            raise Http404 from exc
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
        return redirect("sharing:inbound-detail", capture_id=capture_id)
