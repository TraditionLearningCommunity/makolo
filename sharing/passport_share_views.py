"""Explicit Passport Sharing. Issuance and public visibility are separate."""
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View

from .models import PassportSnapshot, PassportShareSubject, ShareEnvelope, ShareSubjectType
from .passport_views import PassportVerificationView
from .services import ShareUnavailable
from .passport_sharing import create_passport_share, revoke_passport_share, resolve_passport_share


class PassportShareCreateView(LoginRequiredMixin, View):
    """Only the owner or authorized Space manager can share an issued version."""
    def post(self, request, snapshot_id):
        snapshot = get_object_or_404(PassportSnapshot, pk=snapshot_id)
        try:
            days = int(request.POST.get("days", "7"))
            envelope, url = create_passport_share(
                snapshot=snapshot, actor=request.user, days=days,
            )
        except (TypeError, ValueError, ValidationError):
            return render(
                request, "sharing/passport_share_created.html",
                {"error": "Sélection de partage invalide.", "share_url": ""},
                status=400,
            )
        except PermissionDenied as exc:
            raise Http404("Partage indisponible.") from exc
        response = render(
            request, "sharing/passport_share_created.html",
            {
                "share_url": url,
                "document_id": snapshot.document_id,
                "expires_at": envelope.expires_at,
                "history_url": (
                    reverse("sharing:passport-me-history")
                    if snapshot.profile_id
                    else reverse(
                        "sharing:passport-space-history",
                        kwargs={"slug": snapshot.space.slug},
                    )
                ),
            },
        )
        response["Cache-Control"] = "private, no-store"
        return response


class PassportShareRevokeView(LoginRequiredMixin, View):
    """Explicitly revoke one grant, not the underlying issued Passport."""
    def post(self, request, share_id):
        envelope = get_object_or_404(
            ShareEnvelope.objects.filter(subject_type=ShareSubjectType.PASSPORT),
            pk=share_id,
        )
        try:
            snapshot = envelope.passport_subject.snapshot
            revoke_passport_share(envelope=envelope, actor=request.user)
        except (PermissionDenied, PassportShareSubject.DoesNotExist) as exc:
            raise Http404("Partage indisponible.") from exc
        if snapshot.profile_id:
            destination = reverse("sharing:passport-me-history")
        else:
            destination = reverse(
                "sharing:passport-space-history",
                kwargs={"slug": snapshot.space.slug},
            )
        return redirect(destination)


class PassportSharedView(PassportVerificationView):
    """An active Sharing grant reveals only its selected issued document."""
    def get_snapshot(self):
        try:
            self.share_envelope, snapshot = resolve_passport_share(self.kwargs["token"])
            return snapshot
        except ShareUnavailable as exc:
            raise Http404("Ce partage n’est plus disponible.") from exc

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        snapshot = context["snapshot"]
        context.update({
            "is_explicit_share": True,
            "share_expires_at": self.share_envelope.expires_at,
            "can_view_dated_passport": True,
            "dated_payload": snapshot.payload,
            "snapshot_name": snapshot.payload.get(
                "identity", {},
            ).get("name", snapshot.public_identifier),
        })
        return context
