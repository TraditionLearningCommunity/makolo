from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from activities.models import Activity, ActivityStatus, ActivityVisibility

from .forms import DossierCreateForm
from .services import create_dossier


@login_required(login_url="core:login")
def dossier_from_activity(request, activity_id):
    activity = get_object_or_404(
        Activity.objects.select_related("space", "owner_profile"),
        pk=activity_id,
        status=ActivityStatus.PUBLISHED,
        visibility=ActivityVisibility.PUBLIC,
    )
    initial = {
        "title": f"Préparer : {activity.title}"[:220],
        "description": activity.short_description or "",
    }
    form = DossierCreateForm(request.POST or None, actor=request.user, initial=initial)
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
    return render(
        request,
        "objectives/dossier_form.html",
        {"form": form, "source_activity": activity},
    )
