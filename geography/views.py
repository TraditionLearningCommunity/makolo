from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from authorization.constants import PermissionCode
from authorization.services import can
from organizations.models import Organization

from .forms import PlaceForm, SpacePlaceForm
from .models import SpacePlace
from .services import create_place_for_space, deactivate_space_place, update_space_place


class SpacePlaceCreateView(LoginRequiredMixin, View):
    template_name = "geography/space_place_form.html"

    def _organization(self, request, slug):
        organization = get_object_or_404(Organization, slug=slug)
        if not can(request.user, PermissionCode.SPACE_PLACES_MANAGE, organization):
            raise PermissionDenied("Vous ne pouvez pas gérer les Lieux de cet Espace.")
        return organization

    def get(self, request, slug):
        organization = self._organization(request, slug)
        return render(request, self.template_name, {"organization": organization, "space": organization, "place_form": PlaceForm(prefix="place"), "relation_form": SpacePlaceForm(prefix="relation", initial={"is_active": True}), "creating": True})

    def post(self, request, slug):
        organization = self._organization(request, slug)
        place_form = PlaceForm(request.POST, prefix="place")
        relation_form = SpacePlaceForm(request.POST, prefix="relation")
        if place_form.is_valid() and relation_form.is_valid():
            create_place_for_space(actor=request.user, organization=organization, place_data=place_form.cleaned_data, relation_data=relation_form.cleaned_data)
            messages.success(request, "Lieu ajouté à l’Espace.")
            return redirect("organizations:console-places", slug=organization.slug)
        return render(request, self.template_name, {"organization": organization, "space": organization, "place_form": place_form, "relation_form": relation_form, "creating": True}, status=400)


class SpacePlaceUpdateView(LoginRequiredMixin, View):
    template_name = "geography/space_place_form.html"

    def _relation(self, request, slug, pk):
        relation = get_object_or_404(SpacePlace.objects.select_related("organization", "place"), pk=pk, organization__slug=slug)
        if not can(request.user, PermissionCode.SPACE_PLACES_MANAGE, relation.organization):
            raise PermissionDenied("Vous ne pouvez pas gérer les Lieux de cet Espace.")
        return relation

    def get(self, request, slug, pk):
        relation = self._relation(request, slug, pk)
        return render(request, self.template_name, {"organization": relation.organization, "space": relation.organization, "relation": relation, "relation_form": SpacePlaceForm(instance=relation, prefix="relation"), "creating": False})

    def post(self, request, slug, pk):
        relation = self._relation(request, slug, pk)
        form = SpacePlaceForm(request.POST, instance=relation, prefix="relation")
        if form.is_valid():
            update_space_place(actor=request.user, relation=relation, **form.cleaned_data)
            messages.success(request, "Relation du Lieu mise à jour.")
            return redirect("organizations:console-places", slug=relation.organization.slug)
        return render(request, self.template_name, {"organization": relation.organization, "space": relation.organization, "relation": relation, "relation_form": form, "creating": False}, status=400)


class SpacePlaceDeactivateView(LoginRequiredMixin, View):
    def post(self, request, slug, pk):
        relation = get_object_or_404(SpacePlace.objects.select_related("organization"), pk=pk, organization__slug=slug)
        deactivate_space_place(actor=request.user, relation=relation)
        messages.success(request, "Lieu retiré des implantations actives de l’Espace.")
        return redirect("organizations:console-places", slug=relation.organization.slug)
