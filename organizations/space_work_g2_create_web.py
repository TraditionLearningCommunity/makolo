"""MT4 contextual Web creation via the canonical Activity/Services services."""
from django import forms
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404
from django.shortcuts import redirect
from django.urls import reverse

from activities.forms import ActivityCreateForm
from organizations.models import SpaceArchetype
from services.models import ServiceKind

from .space_web_views import SpaceWebMixin
from .space_work_g2_creation import create_g2_owner, g2_creation_available


class SpaceWorkG2CreateView(SpaceWebMixin):
    template_name = "organizations/space/work_g2_create.html"
    space_nav_key = "work"
    space_page_title = "Métier"

    def _allowed(self):
        if (
            self.selected_responsibility["key"] != "all"
            or not g2_creation_available(self.request.user, self.space)
        ):
            raise Http404

    def _form(self, data=None):
        form = ActivityCreateForm(
            data=data, user=self.request.user,
            initial={"organization": self.space.pk, "visibility": "private"},
        )
        form.fields["organization"].widget = forms.HiddenInput()
        if self.space.archetype == SpaceArchetype.SERVICE_PROVIDER:
            form.fields["service_kind"] = forms.ChoiceField(
                label="Type de prestation", choices=ServiceKind.choices,
            )
        return form

    def get_context_data(self, **kwargs):
        self._allowed()
        context = super().get_context_data(**kwargs)
        context.update({
            "create_form": kwargs.get("create_form") or self._form(),
            "create_label": (
                "Nouveau programme"
                if self.space.archetype == SpaceArchetype.EDUCATION
                else "Nouvelle prestation"
            ),
            "is_service": self.space.archetype == SpaceArchetype.SERVICE_PROVIDER,
            "back_url": reverse(
                "organizations:space-work", kwargs={"slug": self.space.slug},
            ),
        })
        return context

    def post(self, request, *args, **kwargs):
        self._allowed()
        # Ownership is decided by the active authorized Space, not the form.
        if request.POST.get("organization") != str(self.space.pk):
            raise PermissionDenied("L'Espace propriétaire ne peut pas être modifié.")
        form = self._form(request.POST)
        if form.is_valid():
            try:
                activity, service = create_g2_owner(
                    actor=request.user, space=self.space,
                    title=form.cleaned_data["title"],
                    short_description=form.cleaned_data["short_description"],
                    description=form.cleaned_data["description"],
                    visibility=form.cleaned_data["visibility"],
                    service_kind=form.cleaned_data.get("service_kind"),
                )
            except (ValidationError, PermissionDenied) as exc:
                form.add_error(
                    None, "; ".join(exc.messages)
                    if hasattr(exc, "messages") else str(exc),
                )
            else:
                messages.success(
                    request,
                    (
                        "Programme créé en brouillon."
                        if service is None else "Prestation créée en brouillon."
                    ),
                )
                return redirect("organizations:space-work", slug=self.space.slug)
        return self.render_to_response(
            self.get_context_data(create_form=form)
        )
