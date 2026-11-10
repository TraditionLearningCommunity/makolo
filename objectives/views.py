from django.contrib import messages
from django.contrib.auth.decorators import login_required as django_login_required
from django.core.exceptions import ObjectDoesNotExist, ValidationError, SuspiciousOperation
from django.http import Http404
from django.db import transaction
from django.shortcuts import redirect, render
from rest_framework.exceptions import ValidationError as APIValidationError
from authorization.constants import PermissionCode
from authorization.services import can
from organizations.models import Organization
from .context import resolve_objective_context
from django.views.decorators.http import require_POST

from .forms import DossierAssignmentForm, DossierAuthorityGrantForm, DossierCreateForm, DossierDependencyForm, DossierDependencyWaiverForm, DossierEditForm, DossierJourneyLinkForm, DossierLifecycleForm, DossierProjectForm, ProjectCreateForm, ProjectDossierLinkForm, ProjectLifecycleForm, ProjectEditForm, ProjectChildDossierForm, ProjectAuthorityGrantForm
from authorization.models import AuthorityScope
from authorization.selectors import current_mandates
from .models import DossierAssignment, DossierJourneyDependencyState
from .readiness import resolve_dossier_readiness
from .dossier_workspace import dossier_workspace
from .project_workspace import project_workspace
from .selectors import active_assignments_for_dossier, active_project_for_dossier, current_dossier_authority_mandates, dossier_for_profile, dossiers_for_profile, project_for_profile, projects_for_profile, visible_dependencies_for_profile, visible_dossiers_for_project, visible_linked_journeys, visible_project_for_dossier
from .services import add_dependency, assign_dossier, can_manage_dossier, can_manage_dossier_authority, can_manage_project, can_manage_project_authority, create_dossier, create_project, dependency_is_satisfied, grant_dossier_authority, grant_project_authority, link_dossier_to_project, link_journey, move_dossier_to_project, remove_dependency, revoke_dossier_authority, revoke_project_authority, set_dossier_lifecycle, set_project_lifecycle, update_project, update_dossier, unassign_dossier, unlink_dossier_from_project, unlink_journey, waive_dependency


login_required = django_login_required(login_url="core:login")


def _web_context(request):
    """Share the API's actor lens without trusting the query as authority."""
    try:
        return resolve_objective_context(request.GET)
    except APIValidationError as exc:
        raise SuspiciousOperation("Contexte Objectives invalide.") from exc


def _web_redirect(request, name, **kwargs):
    response = redirect(name, **kwargs)
    response["Location"] += _web_context(request).query_suffix()
    return response


def _web_creation_space(request, context):
    if context.kind != "space":
        return None
    space = Organization.objects.filter(slug=context.space_slug).first()
    if space is None or not can(request.user, PermissionCode.SPACE_MANAGE, space=space):
        raise Http404
    return space


def _visible_dossier_or_404(profile, dossier_id, actor_context=None):
    queryset = dossiers_for_profile(profile)
    if actor_context is not None:
        queryset = actor_context.filter(queryset)
    try:
        return queryset.get(pk=dossier_id)
    except ObjectDoesNotExist as exc:
        raise Http404 from exc


def _visible_project_or_404(profile, project_id, actor_context=None):
    queryset = projects_for_profile(profile)
    if actor_context is not None:
        queryset = actor_context.filter(queryset)
    try:
        return queryset.get(pk=project_id)
    except ObjectDoesNotExist as exc:
        raise Http404 from exc


def _visible_dependency_or_404(profile, dossier, dependency_id):
    dependency = visible_dependencies_for_profile(profile, dossier).filter(pk=dependency_id).first()
    if dependency is None: raise Http404
    return dependency


@login_required
def organizer(request):
    """One personal organizer; browser interactions operate on the acquired page."""
    from .organizer import build_organizer_page

    context = _web_context(request)
    return render(request, "objectives/organizer.html", {
        "organizer_data": build_organizer_page(
            request.user, limit=50, offset=0, actor_context=context,
        ),
        "scope_query": context.query_suffix(),
        "space_context": context.kind == "space",
    })


@login_required
def dossier_list(request):
    context = _web_context(request)
    return render(request, "objectives/dossier_list.html", {
        "dossiers": context.filter(dossiers_for_profile(request.user)),
        "scope_query": context.query_suffix(),
    })


@login_required
def dossier_create(request):
    context = _web_context(request)
    fixed_space = _web_creation_space(request, context)
    form = DossierCreateForm(request.POST or None, actor=request.user)
    if fixed_space is not None:
        form.fields["owning_space"].initial = fixed_space.pk
        form.fields["owning_space"].disabled = True
    if request.method == "POST" and form.is_valid():
        space = form.cleaned_data["owning_space"]
        dossier = create_dossier(actor=request.user, title=form.cleaned_data["title"], description=form.cleaned_data["description"], owner_profile=None if space else request.user, owning_space=space, deadline=form.cleaned_data["deadline"])
        return _web_redirect(request, "objectives:dossier-detail", dossier_id=dossier.pk)
    return render(request, "objectives/dossier_form.html", {
        "form": form, "space_context_label": fixed_space.name if fixed_space else None,
        "scope_query": context.query_suffix(),
    })


@login_required
def project_list(request):
    context = _web_context(request)
    return render(request, "objectives/project_list.html", {
        "projects": context.filter(projects_for_profile(request.user)),
        "scope_query": context.query_suffix(),
    })


@login_required
def project_create(request):
    context = _web_context(request)
    fixed_space = _web_creation_space(request, context)
    form = ProjectCreateForm(request.POST or None, actor=request.user)
    if fixed_space is not None:
        form.fields["owning_space"].initial = fixed_space.pk
        form.fields["owning_space"].disabled = True
    if request.method == "POST" and form.is_valid():
        space = form.cleaned_data["owning_space"]
        project = create_project(actor=request.user, title=form.cleaned_data["title"], description=form.cleaned_data["description"], owner_profile=None if space else request.user, owning_space=space, starts_on=form.cleaned_data["starts_on"], ends_on=form.cleaned_data["ends_on"])
        return _web_redirect(request, "objectives:project-detail", project_id=project.pk)
    return render(request, "objectives/project_form.html", {
        "form": form, "space_context_label": fixed_space.name if fixed_space else None,
        "scope_query": context.query_suffix(),
    })


@login_required
def project_detail(request, project_id):
    context = _web_context(request)
    project = _visible_project_or_404(request.user, project_id, context)
    workspace = project_workspace(request.user, project, actor_context=context)
    can_manage = can_manage_project(request.user, project)
    return render(request, "objectives/project_detail.html", {
        "project": project,
        "workspace": workspace,
        "scope_query": context.query_suffix(),
        "dossier_rows": workspace["visible_dossiers"],
        "dossiers_page": workspace["dossiers_page"],
        "can_manage": can_manage,
        "access_form": ProjectAuthorityGrantForm() if workspace["collaboration"]["can_manage_authority"] else None,
        "link_form": ProjectDossierLinkForm(
            actor=request.user, actor_context=context,
        ) if "project.dossier.link" in workspace["capabilities"] else None,
        "lifecycle_form": ProjectLifecycleForm(project=project) if can_manage else None,
        "child_form": ProjectChildDossierForm() if "project.dossier.create" in workspace["capabilities"] else None,
        "edit_form": ProjectEditForm(project=project) if can_manage else None,
    })


@login_required
@require_POST
def project_authority(request, project_id):
    """Web submits the same canonical delegation service as the native API."""
    project = _visible_project_or_404(request.user, project_id, _web_context(request))
    if not can_manage_project_authority(request.user, project):
        raise Http404
    if request.POST.get("action") == "grant":
        form = ProjectAuthorityGrantForm(request.POST)
        if form.is_valid():
            try:
                grant_project_authority(
                    actor=request.user, project=project, profile=form.profile,
                    role=form.cleaned_data["role"],
                )
                messages.success(request, "Accès Projet accordé.")
            except ValidationError:
                messages.error(request, "Cet accès Projet n'a pas été accordé.")
        else:
            messages.error(request, "Vérifiez l'adresse du compte et le rôle.")
    elif request.POST.get("action") == "revoke":
        mandate = current_mandates().filter(
            scope_type=AuthorityScope.PROJECT, project=project,
            pk=request.POST.get("mandate_id"),
        ).first()
        if mandate is None:
            raise Http404
        try:
            revoke_project_authority(
                actor=request.user, project=project, mandate=mandate,
            )
            messages.success(request, "Accès Projet retiré.")
        except ValidationError:
            messages.error(request, "Cet accès Projet n'a pas pu être retiré.")
    else:
        raise Http404
    return _web_redirect(request, "objectives:project-detail", project_id=project.pk)


@login_required
def dossier_detail(request, dossier_id):
    context = _web_context(request)
    dossier = _visible_dossier_or_404(request.user, dossier_id, context)
    can_manage = can_manage_dossier(request.user, dossier)
    can_manage_authority = can_manage_dossier_authority(request.user, dossier)
    current_project = active_project_for_dossier(dossier) if can_manage else None
    workspace = dossier_workspace(request.user, dossier, actor_context=context)
    can_manage_project_context = "dossier.project.manage" in workspace["capabilities"]
    return render(request, "objectives/dossier_detail.html", {
        "dossier": dossier,
        "workspace": workspace,
        "scope_query": context.query_suffix(),
        "project": (
            visible_project_for_dossier(request.user, dossier)
            if workspace["parent_project"] is not None else None
        ),
        "can_manage": can_manage,
        "can_manage_authority": can_manage_authority,
        "can_manage_project_context": can_manage_project_context,
        "project_form": DossierProjectForm(
            actor=request.user, current_project=current_project,
            actor_context=context,
        ) if can_manage_project_context else None,
        "edit_form": DossierEditForm(dossier=dossier) if can_manage else None,
        "link_form": DossierJourneyLinkForm(
            actor=request.user, dossier=dossier
        ) if can_manage else None,
        "dependency_form": DossierDependencyForm(
            actor=request.user, dossier=dossier
        ) if can_manage else None,
        "waiver_form": DossierDependencyWaiverForm() if can_manage else None,
        "lifecycle_form": DossierLifecycleForm(
            dossier=dossier
        ) if can_manage else None,
        "assignment_form": DossierAssignmentForm(
            dossier=dossier
        ) if can_manage else None,
        "authority_form": DossierAuthorityGrantForm(
            dossier=dossier
        ) if can_manage_authority else None,
        "assignments": active_assignments_for_dossier(dossier)
                       if can_manage else active_assignments_for_dossier(dossier).filter(
                           assignee=request.user),
        "authority_mandates": current_dossier_authority_mandates(dossier)
                              if can_manage_authority else None,
    })


@login_required
@require_POST
def project_create_child(request, project_id):
    project = _visible_project_or_404(request.user, project_id, _web_context(request))
    if not can_manage_project(request.user, project):
        raise Http404
    form = ProjectChildDossierForm(request.POST)
    if form.is_valid():
        try:
            with transaction.atomic():
                dossier = create_dossier(
                    actor=request.user, title=form.cleaned_data["title"],
                    description=form.cleaned_data["description"],
                    deadline=form.cleaned_data["deadline"],
                    owner_profile=project.owner_profile,
                    owning_space=project.owning_space,
                )
                link_dossier_to_project(
                    actor=request.user, project=project, dossier=dossier,
                )
            messages.success(request, "Dossier créé et rattaché.")
        except ValidationError as exc:
            messages.error(request, exc.messages[0])
    else:
        messages.error(request, "Vérifiez les informations du nouveau Dossier.")
    return _web_redirect(request, "objectives:project-detail", project_id=project.pk)


@login_required
@require_POST
def project_move_dossier(request, project_id, dossier_id):
    project = _visible_project_or_404(request.user, project_id, _web_context(request))
    dossier = _visible_dossier_or_404(request.user, dossier_id, _web_context(request))
    from .models import ProjectDossierLink
    if not ProjectDossierLink.objects.filter(
        project=project, dossier=dossier, is_active=True,
    ).exists():
        raise Http404
    target_id = request.POST.get("target_project_id")
    if not target_id:
        messages.error(request, "Choisissez un Projet cible.")
        return _web_redirect(request, "objectives:project-detail", project_id=project.pk)
    import uuid
    try:
        target_uuid = uuid.UUID(target_id)
    except (TypeError, ValueError, AttributeError):
        raise Http404
    target = _visible_project_or_404(request.user, target_uuid, _web_context(request))
    try:
        move_dossier_to_project(
            actor=request.user, dossier=dossier, target_project=target,
        )
        messages.success(request, "Dossier déplacé sans suppression.")
    except ValidationError as exc:
        messages.error(request, exc.messages[0])
    return _web_redirect(request, "objectives:project-detail", project_id=project.pk)


@login_required
@require_POST
def project_edit(request, project_id):
    project = _visible_project_or_404(request.user, project_id, _web_context(request))
    if not can_manage_project(request.user, project):
        raise Http404
    form = ProjectEditForm(request.POST, project=project)
    if form.is_valid():
        try:
            update_project(actor=request.user, project=project, **form.cleaned_data)
            messages.success(request, "Informations du Projet mises à jour.")
        except ValidationError as exc:
            messages.error(request, exc.messages[0])
    else:
        messages.error(request, "Vérifiez le titre et les dates du Projet.")
    return _web_redirect(request, "objectives:project-detail", project_id=project.pk)


@login_required
@require_POST
def project_link_dossier(request, project_id):
    project = _visible_project_or_404(request.user, project_id, _web_context(request))
    if not can_manage_project(request.user, project): raise Http404
    form = ProjectDossierLinkForm(
        request.POST, actor=request.user, actor_context=_web_context(request),
    )
    if form.is_valid():
        try: link_dossier_to_project(actor=request.user, project=project, dossier=form.cleaned_data["dossier"])
        except ValidationError as exc: messages.error(request, exc.messages[0])
    return _web_redirect(request, "objectives:project-detail", project_id=project.pk)


@login_required
@require_POST
def project_unlink_dossier(request, project_id, dossier_id):
    project = _visible_project_or_404(request.user, project_id, _web_context(request)); dossier = _visible_dossier_or_404(request.user, dossier_id, _web_context(request))
    try: unlink_dossier_from_project(actor=request.user, project=project, dossier=dossier)
    except ValidationError as exc: messages.error(request, exc.messages[0])
    return _web_redirect(request, "objectives:project-detail", project_id=project.pk)


@login_required
@require_POST
def project_lifecycle(request, project_id):
    project = _visible_project_or_404(request.user, project_id, _web_context(request)); form = ProjectLifecycleForm(request.POST, project=project)
    if form.is_valid():
        try: set_project_lifecycle(actor=request.user, project=project, lifecycle=form.cleaned_data["lifecycle"])
        except ValidationError as exc: messages.error(request, exc.messages[0])
    return _web_redirect(request, "objectives:project-detail", project_id=project.pk)


@login_required
@require_POST
def dossier_edit(request, dossier_id):
    dossier = _visible_dossier_or_404(request.user, dossier_id, _web_context(request))
    if not can_manage_dossier(request.user, dossier):
        raise Http404
    form = DossierEditForm(request.POST, dossier=dossier)
    if form.is_valid():
        try:
            update_dossier(
                actor=request.user, dossier=dossier, **form.cleaned_data,
            )
            messages.success(request, "Informations du Dossier mises à jour.")
        except ValidationError as exc:
            messages.error(request, exc.messages[0])
    else:
        messages.error(request, "Vérifiez le titre et l’échéance du Dossier.")
    return _web_redirect(request, "objectives:dossier-detail", dossier_id=dossier.pk)


@login_required
@require_POST
def dossier_project(request, dossier_id):
    dossier = _visible_dossier_or_404(request.user, dossier_id, _web_context(request))
    if not can_manage_dossier(request.user, dossier): raise Http404
    current_project = active_project_for_dossier(dossier)
    if current_project is not None and (
        not can_manage_project(request.user, current_project)
        or not _web_context(request).filter(
            projects_for_profile(request.user).filter(pk=current_project.pk)
        ).exists()
    ): raise Http404
    form = DossierProjectForm(
        request.POST, actor=request.user, current_project=current_project,
        actor_context=_web_context(request),
    )
    if form.is_valid():
        target = form.cleaned_data["project"]
        try:
            if target is None and current_project is not None: unlink_dossier_from_project(actor=request.user, project=current_project, dossier=dossier)
            elif target is not None and current_project is None: link_dossier_to_project(actor=request.user, project=target, dossier=dossier)
            elif target is not None and current_project is not None and target.pk != current_project.pk: move_dossier_to_project(actor=request.user, dossier=dossier, target_project=target)
        except ValidationError as exc: messages.error(request, exc.messages[0])
    return _web_redirect(request, "objectives:dossier-detail", dossier_id=dossier.pk)


@login_required
@require_POST
def dossier_assign(request, dossier_id):
    dossier = _visible_dossier_or_404(request.user, dossier_id, _web_context(request)); form = DossierAssignmentForm(request.POST, dossier=dossier)
    if form.is_valid():
        try: assign_dossier(actor=request.user, dossier=dossier, assignee=form.cleaned_data["assignee"])
        except ValidationError as exc: messages.error(request, exc.messages[0])
    return _web_redirect(request, "objectives:dossier-detail", dossier_id=dossier.pk)


@login_required
@require_POST
def dossier_unassign(request, dossier_id, assignment_id):
    dossier = _visible_dossier_or_404(request.user, dossier_id, _web_context(request)); assignment = DossierAssignment.objects.filter(pk=assignment_id, dossier=dossier).first()
    if assignment is None: raise Http404
    try: unassign_dossier(actor=request.user, dossier=dossier, assignment=assignment)
    except ValidationError as exc: messages.error(request, exc.messages[0])
    return _web_redirect(request, "objectives:dossier-detail", dossier_id=dossier.pk)


@login_required
@require_POST
def dossier_grant_authority(request, dossier_id):
    dossier = _visible_dossier_or_404(request.user, dossier_id, _web_context(request))
    if not can_manage_dossier_authority(request.user, dossier): raise Http404
    form = DossierAuthorityGrantForm(request.POST, dossier=dossier)
    if form.is_valid():
        try: grant_dossier_authority(actor=request.user, dossier=dossier, profile=form.cleaned_data["profile"], role=form.cleaned_data["role"])
        except ValidationError as exc: messages.error(request, exc.messages[0])
    return _web_redirect(request, "objectives:dossier-detail", dossier_id=dossier.pk)


@login_required
@require_POST
def dossier_revoke_authority(request, dossier_id, mandate_id):
    dossier = _visible_dossier_or_404(request.user, dossier_id, _web_context(request))
    if not can_manage_dossier_authority(request.user, dossier): raise Http404
    mandate = current_dossier_authority_mandates(dossier).filter(pk=mandate_id).first()
    if mandate is None: raise Http404
    try: revoke_dossier_authority(actor=request.user, dossier=dossier, mandate=mandate)
    except ValidationError as exc: messages.error(request, exc.messages[0])
    return _web_redirect(request, "objectives:dossier-detail", dossier_id=dossier.pk)


@login_required
@require_POST
def dossier_link_journey(request, dossier_id):
    dossier = _visible_dossier_or_404(request.user, dossier_id, _web_context(request)); form = DossierJourneyLinkForm(request.POST, actor=request.user, dossier=dossier)
    if form.is_valid(): link_journey(actor=request.user, dossier=dossier, journey=form.cleaned_data["journey"])
    return _web_redirect(request, "objectives:dossier-detail", dossier_id=dossier.pk)


@login_required
@require_POST
def dossier_unlink_journey(request, dossier_id, journey_id):
    dossier = _visible_dossier_or_404(request.user, dossier_id, _web_context(request)); link = visible_linked_journeys(request.user, dossier).filter(journey_id=journey_id).first()
    if link is None: raise Http404
    try: unlink_journey(actor=request.user, dossier=dossier, journey=link.journey)
    except ValidationError as exc: messages.error(request, exc.messages[0])
    return _web_redirect(request, "objectives:dossier-detail", dossier_id=dossier.pk)


@login_required
@require_POST
def dossier_add_dependency(request, dossier_id):
    dossier = _visible_dossier_or_404(request.user, dossier_id, _web_context(request))
    if not can_manage_dossier(request.user, dossier): raise Http404
    form = DossierDependencyForm(request.POST, actor=request.user, dossier=dossier)
    if form.is_valid():
        try: add_dependency(actor=request.user, dossier=dossier, dependent_link=form.cleaned_data["dependent_link"], required_link=form.cleaned_data["required_link"])
        except ValidationError as exc: messages.error(request, exc.messages[0])
    return _web_redirect(request, "objectives:dossier-detail", dossier_id=dossier.pk)


@login_required
@require_POST
def dossier_remove_dependency(request, dossier_id, dependency_id):
    dossier = _visible_dossier_or_404(request.user, dossier_id, _web_context(request)); dependency = _visible_dependency_or_404(request.user, dossier, dependency_id)
    try: remove_dependency(actor=request.user, dossier=dossier, dependency=dependency)
    except ValidationError as exc: messages.error(request, exc.messages[0])
    return _web_redirect(request, "objectives:dossier-detail", dossier_id=dossier.pk)


@login_required
@require_POST
def dossier_waive_dependency(request, dossier_id, dependency_id):
    dossier = _visible_dossier_or_404(request.user, dossier_id, _web_context(request)); dependency = _visible_dependency_or_404(request.user, dossier, dependency_id); form = DossierDependencyWaiverForm(request.POST)
    if form.is_valid():
        try: waive_dependency(actor=request.user, dossier=dossier, dependency=dependency, reason=form.cleaned_data["reason"])
        except ValidationError as exc: messages.error(request, exc.messages[0])
    else: messages.error(request, "Une raison courte est requise pour lever ce prérequis.")
    return _web_redirect(request, "objectives:dossier-detail", dossier_id=dossier.pk)


@login_required
@require_POST
def dossier_lifecycle(request, dossier_id):
    dossier = _visible_dossier_or_404(request.user, dossier_id, _web_context(request)); form = DossierLifecycleForm(request.POST, dossier=dossier)
    if form.is_valid():
        try: set_dossier_lifecycle(actor=request.user, dossier=dossier, lifecycle=form.cleaned_data["lifecycle"])
        except ValidationError as exc: messages.error(request, exc.messages[0])
    return _web_redirect(request, "objectives:dossier-detail", dossier_id=dossier.pk)
