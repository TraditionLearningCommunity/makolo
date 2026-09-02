from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.http import Http404
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from .forms import (
    DossierCreateForm,
    DossierDependencyForm,
    DossierDependencyWaiverForm,
    DossierJourneyLinkForm,
    DossierLifecycleForm,
)
from .models import DossierJourneyDependencyState
from .selectors import dossier_for_profile, dossiers_for_profile, visible_dependencies_for_profile, visible_linked_journeys
from .services import (
    add_dependency,
    can_manage_dossier,
    create_dossier,
    dependency_is_satisfied,
    link_journey,
    remove_dependency,
    set_dossier_lifecycle,
    unlink_journey,
    waive_dependency,
)


def _visible_dossier_or_404(profile, dossier_id):
    try:
        return dossier_for_profile(profile, dossier_id)
    except ObjectDoesNotExist as exc:
        raise Http404 from exc


def _visible_dependency_or_404(profile, dossier, dependency_id):
    dependency = visible_dependencies_for_profile(profile, dossier).filter(pk=dependency_id).first()
    if dependency is None:
        raise Http404
    return dependency


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
    dependencies = list(visible_dependencies_for_profile(request.user, dossier))
    for dependency in dependencies:
        dependency.is_satisfied = dependency_is_satisfied(dependency)
    return render(
        request,
        "objectives/dossier_detail.html",
        {
            "dossier": dossier,
            "links": links,
            "dependencies": dependencies,
            "dependency_active_state": DossierJourneyDependencyState.ACTIVE,
            "dependency_waived_state": DossierJourneyDependencyState.WAIVED,
            "can_manage": can_manage,
            "link_form": DossierJourneyLinkForm(actor=request.user, dossier=dossier) if can_manage else None,
            "dependency_form": DossierDependencyForm(actor=request.user, dossier=dossier) if can_manage else None,
            "waiver_form": DossierDependencyWaiverForm() if can_manage else None,
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
    try:
        unlink_journey(actor=request.user, dossier=dossier, journey=link.journey)
    except ValidationError as exc:
        messages.error(request, exc.messages[0])
    return redirect("objectives:dossier-detail", dossier_id=dossier.pk)


@login_required
@require_POST
def dossier_add_dependency(request, dossier_id):
    dossier = _visible_dossier_or_404(request.user, dossier_id)
    if not can_manage_dossier(request.user, dossier):
        raise Http404
    form = DossierDependencyForm(request.POST, actor=request.user, dossier=dossier)
    if form.is_valid():
        try:
            add_dependency(
                actor=request.user,
                dossier=dossier,
                dependent_link=form.cleaned_data["dependent_link"],
                required_link=form.cleaned_data["required_link"],
            )
        except ValidationError as exc:
            messages.error(request, exc.messages[0])
    return redirect("objectives:dossier-detail", dossier_id=dossier.pk)


@login_required
@require_POST
def dossier_remove_dependency(request, dossier_id, dependency_id):
    dossier = _visible_dossier_or_404(request.user, dossier_id)
    dependency = _visible_dependency_or_404(request.user, dossier, dependency_id)
    try:
        remove_dependency(actor=request.user, dossier=dossier, dependency=dependency)
    except ValidationError as exc:
        messages.error(request, exc.messages[0])
    return redirect("objectives:dossier-detail", dossier_id=dossier.pk)


@login_required
@require_POST
def dossier_waive_dependency(request, dossier_id, dependency_id):
    dossier = _visible_dossier_or_404(request.user, dossier_id)
    dependency = _visible_dependency_or_404(request.user, dossier, dependency_id)
    form = DossierDependencyWaiverForm(request.POST)
    if form.is_valid():
        try:
            waive_dependency(
                actor=request.user,
                dossier=dossier,
                dependency=dependency,
                reason=form.cleaned_data["reason"],
            )
        except ValidationError as exc:
            messages.error(request, exc.messages[0])
    else:
        messages.error(request, "Une raison courte est requise pour lever ce prérequis.")
    return redirect("objectives:dossier-detail", dossier_id=dossier.pk)


@login_required
@require_POST
def dossier_lifecycle(request, dossier_id):
    dossier = _visible_dossier_or_404(request.user, dossier_id)
    form = DossierLifecycleForm(request.POST, dossier=dossier)
    if form.is_valid():
        try:
            set_dossier_lifecycle(actor=request.user, dossier=dossier, lifecycle=form.cleaned_data["lifecycle"])
        except ValidationError as exc:
            messages.error(request, exc.messages[0])
    return redirect("objectives:dossier-detail", dossier_id=dossier.pk)
