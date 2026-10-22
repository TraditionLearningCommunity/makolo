"""Template-independent image association management for an Activity."""
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect
from django.views import View

from activities.models import Activity, Occurrence
from authorization.constants import PermissionCode
from authorization.services import can

from .asset_services import create_presentation_asset
from .media_models import PresentationMediaPurpose, PresentationMediaUse
from .media_services import (
    associate_presentation_media, publish_presentation_media, retire_presentation_media,
)


class ActivityMediaAuthorityMixin(LoginRequiredMixin):
    login_url = "core:login"

    def dispatch(self, request, *args, **kwargs):
        self.activity = get_object_or_404(Activity.objects.select_related("space"), pk=kwargs["activity_id"])
        if not can(request.user, PermissionCode.ACTIVITY_MANAGE, activity=self.activity):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)


class ActivityMediaUploadView(ActivityMediaAuthorityMixin, View):
    def post(self, request, *args, **kwargs):
        uploaded = request.FILES.get("image")
        alt_text = (request.POST.get("alt_text") or "").strip()
        if not uploaded or not alt_text:
            messages.error(request, "Une image et sa description accessible sont requises.")
            return redirect("presentations:studio", activity_id=self.activity.pk)
        occurrence_id = request.POST.get("occurrence_id")
        occurrence = None
        if occurrence_id:
            occurrence = get_object_or_404(
                Occurrence, pk=occurrence_id, activity_id=self.activity.pk
            )
        asset = None
        try:
            asset = create_presentation_asset(
                actor=request.user, uploaded_file=uploaded,
                activity=self.activity, owner_space=self.activity.space,
                protected=True,
            )
            media = associate_presentation_media(
                actor=request.user, activity=self.activity, asset=asset,
                occurrence=occurrence, purpose=PresentationMediaPurpose.RECOGNIZE,
                alt_text=alt_text,
            )
            # The editor makes the publication decision explicitly.
            if request.POST.get("publish") == "1":
                publish_presentation_media(actor=request.user, media_use=media)
                messages.success(request, "Image publiée pour cette possibilité.")
            else:
                messages.success(request, "Image enregistrée en brouillon.")
        except (ValidationError, PermissionDenied) as error:
            messages.error(request, str(error))
        return redirect("presentations:studio", activity_id=self.activity.pk)


class ActivityMediaRetireView(ActivityMediaAuthorityMixin, View):
    def post(self, request, *args, **kwargs):
        media = get_object_or_404(
            PresentationMediaUse, pk=kwargs["use_id"], activity_id=self.activity.pk
        )
        try:
            retire_presentation_media(actor=request.user, media_use=media)
            messages.success(request, "Image retirée de la présentation publique.")
        except ValidationError as error:
            messages.error(request, str(error))
        return redirect("presentations:studio", activity_id=self.activity.pk)
