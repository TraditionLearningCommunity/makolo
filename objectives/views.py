from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.http import Http404
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from .forms import DossierAssignmentForm, DossierAuthorityGrantForm, DossierCreateForm, DossierDependencyForm, DossierDependencyWaiverForm, DossierJourneyLinkForm, DossierLifecycleForm, DossierProjectForm, ProjectCreateForm, ProjectDossierLinkForm, ProjectLifecycleForm
from .models import DossierAssignment, DossierJourneyDependencyState
from .readiness import resolve_dossier_readiness
from .selectors import active_assignments_for_dossier, active_project_for_dossier, current_dossier_authority_mandates, dossier_for_profile, dossiers_for_profile, project_for_profile, projects_for_profile, visible_dependencies_for_profile, visible_dossiers_for_project, visible_linked_journeys, visible_project_for_dossier
from .services import add_dependency, assign_dossier, can_manage_dossier, can_manage_dossier_authority, can_manage_project, create_dossier, create_project, dependency_is_satisfied, grant_dossier_authority, link_dossier_to_project, link_journey, move_dossier_to_project, remove_dependency, revoke_dossier_authority, set_dossier_lifecycle, set_project_lifecycle, unassign_dossier, unlink_dossier_from_project, unlink_journey, waive_dependency


def _visible_dossier_or_404(profile, dossier_id):
    try: return dossier_for_profile(profile, dossier_id)
    except ObjectDoesNotExist as exc: raise Http404 from exc


def _visible_project_or_404(profile, project_id):
    try: return project_for_profile(profile, project_id)
    except ObjectDoesNotExist as exc: raise Http404 from exc


def _visible_dependency_or_404(profile, dossier, dependency_id):
    dependency = visible_dependencies_for_profile(profile, dossier).filter(pk=dependency_id).first()
    if dependency is None: raise Http404
    return dependency


@login_required
def dossier_list(request): return render(request, "objectives/dossier_list.html", {"dossiers": dossiers_for_profile(request.user)})


@login_required
def dossier_create(request):
    form = DossierCreateForm(request.POST or None, actor=request.user)
    if request.method == "POST" and form.is_valid():
        space = form.cleaned_data["owning_space"]
        dossier = create_dossier(actor=request.user, title=form.cleaned_data["title"], description=form.cleaned_data["description"], owner_profile=None if space else request.user, owning_space=space, deadline=form.cleaned_data["deadline"])
        return redirect("objectives:dossier-detail", dossier_id=dossier.pk)
    return render(request, "objectives/dossier_form.html", {"form": form})


@login_required
def project_list(request): return render(request, "objectives/project_list.html", {"projects": projects_for_profile(request.user)})


@login_required
def project_create(request):
    form = ProjectCreateForm(request.POST or None, actor=request.user)
    if request.method == "POST" and form.is_valid():
        space = form.cleaned_data["owning_space"]
        project = create_project(actor=request.user, title=form.cleaned_data["title"], description=form.cleaned_data["description"], owner_profile=None if space else request.user, owning_space=space, starts_on=form.cleaned_data["starts_on"], ends_on=form.cleaned_data["ends_on"])
        return redirect("objectives:project-detail", project_id=project.pk)
    return render(request, "objectives/project_form.html", {"form": form})


@login_required
def project_detail(request, project_id):
    project = _visible_project_or_404(request.user, project_id); can_manage = can_manage_project(request.user, project)
    dossiers = list(visible_dossiers_for_project(request.user, project)[:50])
    dossier_rows = [{"dossier": dossier, "readiness": resolve_dossier_readiness(dossier, viewer=request.user), "can_manage": can_manage_dossier(request.user, dossier)} for dossier in dossiers]
    return render(request, "objectives/project_detail.html", {"project": project, "dossier_rows": dossier_rows, "visible_dossier_count": visible_dossiers_for_project(request.user, project).count(), "can_manage": can_manage, "link_form": ProjectDossierLinkForm(actor=request.user) if can_manage else None, "lifecycle_form": ProjectLifecycleForm(project=project) if can_manage else None})


@login_required
def dossier_detail(request, dossier_id):
    dossier = _visible_dossier_or_404(request.user, dossier_id); can_manage = can_manage_dossier(request.user, dossier); can_manage_authority = can_manage_dossier_authority(request.user, dossier)
    links = visible_linked_journeys(request.user, dossier); dependencies = list(visible_dependencies_for_profile(request.user, dossier))
    for dependency in dependencies: dependency.is_satisfied = dependency_is_satisfied(dependency)
    visible_project = visible_project_for_dossier(request.user, dossier); current_project = active_project_for_dossier(dossier) if can_manage else None
    can_manage_project_context = can_manage and (current_project is None or can_manage_project(request.user, current_project))
    return render(request, "objectives/dossier_detail.html", {
        "dossier": dossier, "links": links, "dependencies": dependencies, "assignments": active_assignments_for_dossier(dossier),
        "collective_readiness": resolve_dossier_readiness(dossier, viewer=request.user), "project": visible_project,
        "authority_mandates": current_dossier_authority_mandates(dossier) if can_manage_authority else None,
        "dependency_active_state": DossierJourneyDependencyState.ACTIVE, "dependency_waived_state": DossierJourneyDependencyState.WAIVED,
        "can_manage": can_manage, "can_manage_authority": can_manage_authority, "can_manage_project_context": can_manage_project_context,
        "project_form": DossierProjectForm(actor=request.user, current_project=current_project) if can_manage_project_context else None,
        "link_form": DossierJourneyLinkForm(actor=request.user, dossier=dossier) if can_manage else None,
        "dependency_form": DossierDependencyForm(actor=request.user, dossier=dossier) if can_manage else None,
        "waiver_form": DossierDependencyWaiverForm() if can_manage else None,
        "lifecycle_form": DossierLifecycleForm(dossier=dossier) if can_manage else None,
        "assignment_form": DossierAssignmentForm(dossier=dossier) if can_manage else None,
        "authority_form": DossierAuthorityGrantForm(dossier=dossier) if can_manage_authority else None,
    })


@login_required
@require_POST
def project_link_dossier(request, project_id):
    project = _visible_project_or_404(request.user, project_id)
    if not can_manage_project(request.user, project): raise Http404
    form = ProjectDossierLinkForm(request.POST, actor=request.user)
    if form.is_valid():
        try: link_dossier_to_project(actor=request.user, project=project, dossier=form.cleaned_data["dossier"])
        except ValidationError as exc: messages.error(request, exc.messages[0])
    return redirect("objectives:project-detail", project_id=project.pk)


@login_required
@require_POST
def project_unlink_dossier(request, project_id, dossier_id):
    project = _visible_project_or_404(request.user, project_id); dossier = _visible_dossier_or_404(request.user, dossier_id)
    try: unlink_dossier_from_project(actor=request.user, project=project, dossier=dossier)
    except ValidationError as exc: messages.error(request, exc.messages[0])
    return redirect("objectives:project-detail", project_id=project.pk)


@login_required
@require_POST
def project_lifecycle(request, project_id):
    project = _visible_project_or_404(request.user, project_id); form = ProjectLifecycleForm(request.POST, project=project)
    if form.is_valid():
        try: set_project_lifecycle(actor=request.user, project=project, lifecycle=form.cleaned_data["lifecycle"])
        except ValidationError as exc: messages.error(request, exc.messages[0])
    return redirect("objectives:project-detail", project_id=project.pk)


@login_required
@require_POST
def dossier_project(request, dossier_id):
    dossier = _visible_dossier_or_404(request.user, dossier_id)
    if not can_manage_dossier(request.user, dossier): raise Http404
    current_project = active_project_for_dossier(dossier)
    if current_project is not None and not can_manage_project(request.user, current_project): raise Http404
    form = DossierProjectForm(request.POST, actor=request.user, current_project=current_project)
    if form.is_valid():
        target = form.cleaned_data["project"]
        try:
            if target is None and current_project is not None: unlink_dossier_from_project(actor=request.user, project=current_project, dossier=dossier)
            elif target is not None and current_project is None: link_dossier_to_project(actor=request.user, project=target, dossier=dossier)
            elif target is not None and current_project is not None and target.pk != current_project.pk: move_dossier_to_project(actor=request.user, dossier=dossier, target_project=target)
        except ValidationError as exc: messages.error(request, exc.messages[0])
    return redirect("objectives:dossier-detail", dossier_id=dossier.pk)


@login_required
@require_POST
def dossier_assign(request, dossier_id):
    dossier = _visible_dossier_or_404(request.user, dossier_id); form = DossierAssignmentForm(request.POST, dossier=dossier)
    if form.is_valid():
        try: assign_dossier(actor=request.user, dossier=dossier, assignee=form.cleaned_data["assignee"])
        except ValidationError as exc: messages.error(request, exc.messages[0])
    return redirect("objectives:dossier-detail", dossier_id=dossier.pk)


@login_required
@require_POST
def dossier_unassign(request, dossier_id, assignment_id):
    dossier = _visible_dossier_or_404(request.user, dossier_id); assignment = DossierAssignment.objects.filter(pk=assignment_id, dossier=dossier).first()
    if assignment is None: raise Http404
    try: unassign_dossier(actor=request.user, dossier=dossier, assignment=assignment)
    except ValidationError as exc: messages.error(request, exc.messages[0])
    return redirect("objectives:dossier-detail", dossier_id=dossier.pk)


@login_required
@require_POST
def dossier_grant_authority(request, dossier_id):
    dossier = _visible_dossier_or_404(request.user, dossier_id)
    if not can_manage_dossier_authority(request.user, dossier): raise Http404
    form = DossierAuthorityGrantForm(request.POST, dossier=dossier)
    if form.is_valid():
        try: grant_dossier_authority(actor=request.user, dossier=dossier, profile=form.cleaned_data["profile"], role=form.cleaned_data["role"])
        except ValidationError as exc: messages.error(request, exc.messages[0])
    return redirect("objectives:dossier-detail", dossier_id=dossier.pk)


@login_required
@require_POST
def dossier_revoke_authority(request, dossier_id, mandate_id):
    dossier = _visible_dossier_or_404(request.user, dossier_id)
    if not can_manage_dossier_authority(request.user, dossier): raise Http404
    mandate = current_dossier_authority_mandates(dossier).filter(pk=mandate_id).first()
    if mandate is None: raise Http404
    try: revoke_dossier_authority(actor=request.user, dossier=dossier, mandate=mandate)
    except ValidationError as exc: messages.error(request, exc.messages[0])
    return redirect("objectives:dossier-detail", dossier_id=dossier.pk)


@login_required
@require_POST
def dossier_link_journey(request, dossier_id):
    dossier = _visible_dossier_or_404(request.user, dossier_id); form = DossierJourneyLinkForm(request.POST, actor=request.user, dossier=dossier)
    if form.is_valid(): link_journey(actor=request.user, dossier=dossier, journey=form.cleaned_data["journey"])
    return redirect("objectives:dossier-detail", dossier_id=dossier.pk)


@login_required
@require_POST
def dossier_unlink_journey(request, dossier_id, journey_id):
    dossier = _visible_dossier_or_404(request.user, dossier_id); link = visible_linked_journeys(request.user, dossier).filter(journey_id=journey_id).first()
    if link is None: raise Http404
    try: unlink_journey(actor=request.user, dossier=dossier, journey=link.journey)
    except ValidationError as exc: messages.error(request, exc.messages[0])
    return redirect("objectives:dossier-detail", dossier_id=dossier.pk)


@login_required
@require_POST
def dossier_add_dependency(request, dossier_id):
    dossier = _visible_dossier_or_404(request.user, dossier_id)
    if not can_manage_dossier(request.user, dossier): raise Http404
    form = DossierDependencyForm(request.POST, actor=request.user, dossier=dossier)
    if form.is_valid():
        try: add_dependency(actor=request.user, dossier=dossier, dependent_link=form.cleaned_data["dependent_link"], required_link=form.cleaned_data["required_link"])
        except ValidationError as exc: messages.error(request, exc.messages[0])
    return redirect("objectives:dossier-detail", dossier_id=dossier.pk)


@login_required
@require_POST
def dossier_remove_dependency(request, dossier_id, dependency_id):
    dossier = _visible_dossier_or_404(request.user, dossier_id); dependency = _visible_dependency_or_404(request.user, dossier, dependency_id)
    try: remove_dependency(actor=request.user, dossier=dossier, dependency=dependency)
    except ValidationError as exc: messages.error(request, exc.messages[0])
    return redirect("objectives:dossier-detail", dossier_id=dossier.pk)


@login_required
@require_POST
def dossier_waive_dependency(request, dossier_id, dependency_id):
    dossier = _visible_dossier_or_404(request.user, dossier_id); dependency = _visible_dependency_or_404(request.user, dossier, dependency_id); form = DossierDependencyWaiverForm(request.POST)
    if form.is_valid():
        try: waive_dependency(actor=request.user, dossier=dossier, dependency=dependency, reason=form.cleaned_data["reason"])
        except ValidationError as exc: messages.error(request, exc.messages[0])
    else: messages.error(request, "Une raison courte est requise pour lever ce prérequis.")
    return redirect("objectives:dossier-detail", dossier_id=dossier.pk)


@login_required
@require_POST
def dossier_lifecycle(request, dossier_id):
    dossier = _visible_dossier_or_404(request.user, dossier_id); form = DossierLifecycleForm(request.POST, dossier=dossier)
    if form.is_valid():
        try: set_dossier_lifecycle(actor=request.user, dossier=dossier, lifecycle=form.cleaned_data["lifecycle"])
        except ValidationError as exc: messages.error(request, exc.messages[0])
    return redirect("objectives:dossier-detail", dossier_id=dossier.pk)
