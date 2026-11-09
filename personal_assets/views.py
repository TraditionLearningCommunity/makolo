from datetime import timedelta

from urllib.parse import urlsplit

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import F, OuterRef, Subquery
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from journeys.collaboration_models import JourneyArtifact, JourneyArtifactKind, JourneyArtifactSensitivity
from journeys.collaboration_services import artifact_for_download, ensure_case_access
from journeys.models import Journey
from journeys.selectors import journeys_for_profile
from trust.credential_selectors import credentials_for_profile
from trust.selectors import proofs_for_profile

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


def _private_render(request, template_name, context=None, **kwargs):
    response = render(request, template_name, context, **kwargs)
    response["Cache-Control"] = "private, no-store"
    return response


def _safe_collection_return(request, candidate, *, fallback):
    candidate = (candidate or "").strip()
    if not candidate:
        return fallback
    parsed = urlsplit(candidate)
    if parsed.scheme or parsed.netloc or parsed.fragment or parsed.path != fallback:
        return fallback
    return candidate


def _latest_version(asset):
    versions = list(personal_asset_versions_for_controller(asset.controller, asset).order_by("-version")[:1])
    return versions[0] if versions else None


def _asset_for_request(request, asset_id, *, include_archived=False):
    assets = PersonalAsset.objects.filter(controller=request.user)
    if not include_archived:
        assets = assets.filter(archived_at__isnull=True)
    return get_object_or_404(assets, pk=asset_id)


@login_required
def resources_hub(request):
    return _private_render(
        request,
        "personal_assets/hub.html",
        {
            "document_count": personal_assets_for_controller(request.user).count(),
            "proof_count": proofs_for_profile(request.user).count(),
            "credential_count": credentials_for_profile(request.user).count(),
        },
    )


@login_required
def library_list(request):
    query = (request.GET.get("q") or "").strip()[:120]
    active_view = request.GET.get("view", "current")
    active_sort = request.GET.get("sort", "recent")
    kind = request.GET.get("kind", "")
    sensitivity = request.GET.get("sensitivity", "")

    if active_view not in {"current", "expiring", "archived"}:
        active_view = "current"
    if active_sort not in {"recent", "oldest", "title", "expiry"}:
        active_sort = "recent"
    valid_kinds = {value for value, _label in JourneyArtifactKind.choices}
    valid_sensitivities = {
        value for value, _label in JourneyArtifactSensitivity.choices
    }
    if kind not in valid_kinds:
        kind = ""
    if sensitivity not in valid_sensitivities:
        sensitivity = ""

    latest = PersonalAssetVersion.objects.filter(
        asset_id=OuterRef("pk"),
    ).order_by("-version", "-created_at")
    assets = personal_assets_for_controller(
        request.user,
        include_archived=active_view == "archived",
    ).filter(archived_at__isnull=(active_view != "archived"))
    assets = assets.annotate(
        current_expires_at=Subquery(latest.values("expires_at")[:1]),
    )

    if query:
        assets = assets.filter(title__icontains=query)
    if kind:
        assets = assets.filter(kind=kind)
    if sensitivity:
        assets = assets.filter(sensitivity=sensitivity)
    if active_view == "expiring":
        today = timezone.localdate()
        assets = assets.filter(
            current_expires_at__gte=today,
            current_expires_at__lte=today + timedelta(days=30),
        )

    if active_sort == "oldest":
        assets = assets.order_by("updated_at", "id")
    elif active_sort == "title":
        assets = assets.order_by("title", "id")
    elif active_sort == "expiry":
        assets = assets.order_by(
            F("current_expires_at").asc(nulls_last=True),
            "title",
            "id",
        )
    else:
        assets = assets.order_by("-updated_at", "id")

    page = Paginator(assets, 24).get_page(request.GET.get("page"))
    items = [
        {"asset": asset, "latest": _latest_version(asset)}
        for asset in page.object_list
    ]
    return _private_render(
        request,
        "personal_assets/list.html",
        {
            "items": items,
            "page": page,
            "query": query,
            "active_view": active_view,
            "active_sort": active_sort,
            "kind": kind,
            "sensitivity": sensitivity,
            "kind_options": JourneyArtifactKind.choices,
            "sensitivity_options": JourneyArtifactSensitivity.choices,
            "today": timezone.localdate(),
        },
    )


@login_required
def library_detail(request, asset_id):
    asset = _asset_for_request(request, asset_id, include_archived=True)
    versions = list(personal_asset_versions_for_controller(request.user, asset).order_by("-version"))
    latest = versions[0] if versions else None
    fallback = reverse("personal_assets:documents")
    return _private_render(
        request,
        "personal_assets/detail.html",
        {
            "asset": asset,
            "versions": versions,
            "latest": latest,
            "today": timezone.localdate(),
            "return_url": _safe_collection_return(
                request,
                request.GET.get("return"),
                fallback=fallback,
            ),
        },
    )


@login_required
def library_reuse(request, asset_id):
    asset = _asset_for_request(request, asset_id)
    version = _latest_version(asset)
    if version is None:
        raise Http404

    journeys = []
    for journey in journeys_for_profile(request.user).order_by("-updated_at", "id"):
        try:
            ensure_case_access(request.user, journey, write=False)
        except PermissionDenied:
            continue
        journeys.append(journey)

    if request.method == "POST":
        journey = next(
            (
                candidate
                for candidate in journeys
                if str(candidate.pk) == (request.POST.get("journey_id") or "")
            ),
            None,
        )
        if journey is None:
            raise Http404
        try:
            artifact = use_personal_asset_version_in_journey(
                actor=request.user,
                personal_asset_version=version,
                journey=journey,
            )
        except (PermissionDenied, ValidationError) as exc:
            messages.error(request, str(exc))
        else:
            messages.success(
                request,
                "Ajouté à la démarche.",
            )
            return redirect("core:participant-journey-detail", pk=journey.pk)

    return _private_render(
        request,
        "personal_assets/reuse.html",
        {"asset": asset, "version": version, "journeys": journeys},
    )


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
            messages.success(request, "Document ajouté.")
            return redirect("personal_assets:detail", asset_id=asset.pk)
        except ValidationError as exc:
            form.add_error(None, exc)
    return _private_render(request, "personal_assets/form.html", {"form": form, "heading": "Ajouter un document", "submit_label": "Ajouter"})


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
            messages.success(request, f"Version {version.version} ajoutée.")
            return redirect("personal_assets:detail", asset_id=asset.pk)
        except ValidationError as exc:
            form.add_error(None, exc)
    return _private_render(request, "personal_assets/form.html", {"form": form, "heading": f"Nouvelle version — {asset.title}", "submit_label": "Créer la nouvelle version", "asset": asset})


@login_required
@require_POST
def library_archive(request, asset_id):
    asset = _asset_for_request(request, asset_id)
    archive_personal_asset(actor=request.user, asset=asset)
    messages.success(request, "Document archivé.")
    return redirect("personal_assets:documents")


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
            messages.success(request, "Document ajouté à la démarche.")
            return redirect("journeys:artifact-download", artifact_id=artifact.pk)
    return _private_render(request, "personal_assets/use_in_journey.html", {"journey": journey, "items": items})


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
    return _private_render(request, "personal_assets/save_artifact.html", {"artifact": artifact, "form": form, "assets": assets})
