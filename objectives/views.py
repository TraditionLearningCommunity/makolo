from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist
from django.http import Http404
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from .forms import DossierCreateForm, DossierJourneyLinkForm, DossierLifecycleForm
from .selectors import dossier_for_profile, dossiers_for_profile, visible_linked_journeys
from .services import can_manage_dossier, create_dossier, link_journey, set_dossier_lifecycle, unlink_journey


def _visible_dossier_or_404(profile, dossier_id):
    try:
        return dossier_for_profile(profile, dossier_id)
    except ObjectDoesNotExist as exc:
        raise Http404 from exc


@login_required
def dossier_list(request):
    return render(request, "objectives/dossier_list.html", {"dossiers": dossiers_for_profile(request.user)})


@login_required
def dossier_create(request):
    form = DossierCreateForm(request.POST or None, actor=request.user)
    if request.method == "POST" and form.is_valid():
        space = form.cleaned_data["owning_space"]
        dossier = create_dossier(
            actor=request.user,
            title=form.cleaned_data["title"],
            description=form.cleaned_data["description"],
            owner_profile=None if space else request.user,
            owning_space=space,
            deadline=form.cleaned_data["deadline"],
        )
        return redirect("objectives:dossier-detail", dossier_id=dossier.pk)
    return render(request, "objectives/dossier_form.html", {"form": form})


@login_required
def dossier_detail(request, dossier_id):
    dossier = _visible_dossier_or_404(request.user, dossier_id)
    can_manage = can_manage_dossier(request.user, dossier)
    links = visible_linked_journeys(request.user, dossier)
    return render(
        request,
        "objectives/dossier_detail.html",
        {
            "dossier": dossier,
            "links": links,
            "can_manage": can_manage,
            "link_form": DossierJourneyLinkForm(actor=request.user, dossier=dossier) if can_manage else None,
            "lifecycle_form": DossierLifecycleForm(dossier=dossier) if can_manage else None,
        },
    )


@login_required
@require_POST
def dossier_link_journey(request, dossier_id):
    dossier = _visible_dossier_or_404(request.user, dossier_id)
    form = DossierJourneyLinkForm(request.POST, actor=request.user, dossier=dossier)
    if form.is_valid():
        link_journey(actor=request.user, dossier=dossier, journey=form.cleaned_data["journey"])
    return redirect("objectives:dossier-detail", dossier_id=dossier.pk)


@login_required
@require_POST
def dossier_unlink_journey(request, dossier_id, journey_id):
    dossier = _visible_dossier_or_404(request.user, dossier_id)
    link = visible_linked_journeys(request.user, dossier).filter(journey_id=journey_id).first()
    if link is None:
        raise Http404
    unlink_journey(actor=request.user, dossier=dossier, journey=link.journey)
    return redirect("objectives:dossier-detail", dossier_id=dossier.pk)


@login_required
@require_POST
def dossier_lifecycle(request, dossier_id):
    dossier = _visible_dossier_or_404(request.user, dossier_id)
    form = DossierLifecycleForm(request.POST, dossier=dossier)
    if form.is_valid():
        set_dossier_lifecycle(actor=request.user, dossier=dossier, lifecycle=form.cleaned_data["lifecycle"])
    return redirect("objectives:dossier-detail", dossier_id=dossier.pk)
