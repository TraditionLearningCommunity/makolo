from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from journeys.collaboration_models import JourneyArtifact
from journeys.collaboration_services import artifact_for_download, ensure_case_access
from journeys.models import Journey

from .forms import PersonalAssetCreateForm, PersonalAssetVersionForm, SaveArtifactToLibraryForm
from .models import PersonalAsset, PersonalAssetVersion
from .selectors import personal_assets_for_controller, personal_asset_versions_for_controller
from .services import (
    archive_personal_asset,
    create_personal_asset,
    create_personal_asset_version,
    personal_asset_version_for_download,
    save_journey_artifact_to_library,
    use_personal_asset_version_in_journey,
)


def _latest_version(asset):
    versions = list(personal_asset_versions_for_controller(asset.controller, asset).order_by("-version")[:1])
    return versions[0] if versions else None


def _asset_for_request(request, asset_id):
    return get_object_or_404(PersonalAsset.objects.filter(controller=request.user, archived_at__isnull=True), pk=asset_id)


@login_required
def library_list(request):
    assets = personal_assets_for_controller(request.user)
    active_filter = request.GET.get("filter", "all")
    if active_filter == "expiring":
        today = timezone.localdate()
        assets = assets.filter(versions__expires_at__gte=today, versions__expires_at__lte=today + timedelta(days=30)).distinct()
    items = [{"asset": asset, "latest": _latest_version(asset)} for asset in assets]
    return render(request, "personal_assets/list.html", {"items": items, "active_filter": active_filter})


@login_required
def library_detail(request, asset_id):
    asset = _asset_for_request(request, asset_id)
    versions = list(personal_asset_versions_for_controller(request.user, asset).order_by("-version"))
    latest = versions[0] if versions else None
    return render(request, "personal_assets/detail.html", {"asset": asset, "versions": versions, "latest": latest, "today": timezone.localdate()})


@login_required
def library_add(request):
    form = PersonalAssetCreateForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                asset = create_personal_asset(
                    controller=request.user,
                    subject_profile=request.user,
                    title=form.cleaned_data["title"],
                    kind=form.cleaned_data["kind"],
                    sensitivity=form.cleaned_data["sensitivity"],
                )
                create_personal_asset_version(
                    actor=request.user,
                    asset=asset,
                    uploaded_file=form.cleaned_data["file"],
                    issued_at=form.cleaned_data["issued_at"],
                    expires_at=form.cleaned_data["expires_at"],
                )
            messages.success(request, "Document ajouté à Ma Bibliothèque.")
            return redirect("personal_assets:detail", asset_id=asset.pk)
        except ValidationError as exc:
            form.add_error(None, exc)
    return render(request, "personal_assets/form.html", {"form": form, "heading": "Ajouter un document", "submit_label": "Ajouter"})


@login_required
def library_add_version(request, asset_id):
    asset = _asset_for_request(request, asset_id)
    form = PersonalAssetVersionForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        try:
            version = create_personal_asset_version(
                actor=request.user,
                asset=asset,
                uploaded_file=form.cleaned_data["file"],
                issued_at=form.cleaned_data["issued_at"],
                expires_at=form.cleaned_data["expires_at"],
            )
            messages.success(request, f"Version {version.version} ajoutée sans écraser l’historique.")
            return redirect("personal_assets:detail", asset_id=asset.pk)
        except ValidationError as exc:
            form.add_error(None, exc)
    return render(request, "personal_assets/form.html", {"form": form, "heading": f"Nouvelle version — {asset.title}", "submit_label": "Créer la nouvelle version", "asset": asset})


@login_required
@require_POST
def library_archive(request, asset_id):
    asset = _asset_for_request(request, asset_id)
    archive_personal_asset(actor=request.user, asset=asset)
    messages.success(request, "Élément archivé. Son historique est conservé.")
    return redirect("personal_assets:list")


@login_required
def library_download(request, version_id):
    version = personal_asset_version_for_download(actor=request.user, version_id=version_id)
    response = FileResponse(version.file.open("rb"), as_attachment=True, filename=f"{slugify(version.asset.title) or 'document'}-v{version.version}", content_type=version.mime_type)
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "private, no-store"
    return response


@login_required
def library_use_in_journey(request, journey_id):
    journey = get_object_or_404(Journey.objects.select_related("activity"), pk=journey_id)
    try:
        ensure_case_access(request.user, journey, write=False)
    except PermissionDenied as exc:
        raise Http404 from exc
    assets = personal_assets_for_controller(request.user)
    items = []
    for asset in assets:
        versions = list(personal_asset_versions_for_controller(request.user, asset).order_by("-version"))
        if versions:
            items.append({"asset": asset, "versions": versions})
    if request.method == "POST":
        version = get_object_or_404(PersonalAssetVersion.objects.select_related("asset").filter(asset__controller=request.user, asset__archived_at__isnull=True), pk=request.POST.get("version_id"))
        try:
            artifact = use_personal_asset_version_in_journey(actor=request.user, personal_asset_version=version, journey=journey)
        except (PermissionDenied, ValidationError) as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, f"Version {version.version} utilisée comme snapshot dans la démarche.")
            return redirect("journeys:artifact-download", artifact_id=artifact.pk)
    return render(request, "personal_assets/use_in_journey.html", {"journey": journey, "items": items})


@login_required
def journey_artifact_save_to_library(request, artifact_id):
    try:
        artifact = artifact_for_download(actor=request.user, artifact_id=artifact_id)
    except PermissionDenied as exc:
        raise Http404 from exc
    assets = list(personal_assets_for_controller(request.user))
    form = SaveArtifactToLibraryForm(request.POST or None, initial={"title": artifact.title, "kind": artifact.kind})
    if request.method == "POST" and form.is_valid():
        target = None
        if form.cleaned_data["mode"] == SaveArtifactToLibraryForm.MODE_EXISTING:
            target = get_object_or_404(PersonalAsset.objects.filter(controller=request.user, archived_at__isnull=True), pk=form.cleaned_data["existing_asset_id"])
        try:
            version = save_journey_artifact_to_library(
                actor=request.user,
                journey_artifact=artifact,
                asset=target,
                title=form.cleaned_data["title"] or artifact.title,
                kind=form.cleaned_data["kind"] or artifact.kind,
                issued_at=form.cleaned_data["issued_at"],
                expires_at=form.cleaned_data["expires_at"],
            )
        except (PermissionDenied, ValidationError) as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, "Artifact conservé dans Ma Bibliothèque sans modifier la Journey.")
            return redirect("personal_assets:detail", asset_id=version.asset_id)
    return render(request, "personal_assets/save_artifact.html", {"artifact": artifact, "form": form, "assets": assets})
