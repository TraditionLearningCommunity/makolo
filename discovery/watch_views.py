from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.http import Http404
from django.shortcuts import redirect
from django.urls import reverse
from django.views import View
from django.views.generic import ListView, TemplateView

from .models import DiscoveryWatch, DiscoveryWatchStatus
from .watch_forms import DiscoveryWatchCreateForm, DiscoveryWatchEditForm
from .watches import criteria_from_discovery_params, execute_watch, suggest_watch_name, watch_query_string


class OwnedWatchMixin(LoginRequiredMixin):
    login_url = "core:login"

    def get_watch(self):
        try:
            return DiscoveryWatch.objects.select_related("dossier").get(pk=self.kwargs["watch_id"], owner=self.request.user)
        except DiscoveryWatch.DoesNotExist as exc:
            raise Http404 from exc


class WatchListView(LoginRequiredMixin, ListView):
    login_url = "core:login"
    model = DiscoveryWatch
    template_name = "discovery/watch_list.html"
    context_object_name = "watches"
    paginate_by = 30

    def get_queryset(self):
        return DiscoveryWatch.objects.filter(owner=self.request.user).select_related("dossier")


class WatchCreateView(LoginRequiredMixin, TemplateView):
    login_url = "core:login"
    template_name = "discovery/watch_create.html"

    def get(self, request, *args, **kwargs):
        try:
            criteria = criteria_from_discovery_params(request.GET)
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
            return redirect("discovery:home")
        form = DiscoveryWatchCreateForm(user=request.user, initial={"criteria": criteria, "name": suggest_watch_name(criteria)})
        return self.render_to_response(self.get_context_data(form=form, criteria=criteria))

    def post(self, request, *args, **kwargs):
        form = DiscoveryWatchCreateForm(request.POST, user=request.user)
        if form.is_valid():
            watch = form.save()
            messages.success(request, "Veille enregistrée.")
            return redirect("discovery:watch-detail", watch_id=watch.pk)
        return self.render_to_response(self.get_context_data(form=form), status=400)


class WatchDetailView(OwnedWatchMixin, TemplateView):
    template_name = "discovery/watch_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        watch = self.get_watch()
        errors = []
        try:
            result = execute_watch(watch.criteria, profile=self.request.user)
        except ValidationError as exc:
            result = None
            errors = exc.messages
        context.update({"watch": watch, "result": result, "search_errors": errors, "discover_url": reverse("discovery:home") + "?" + watch_query_string(watch.criteria)})
        return context


class WatchEditView(OwnedWatchMixin, TemplateView):
    template_name = "discovery/watch_edit.html"

    def get(self, request, *args, **kwargs):
        watch = self.get_watch()
        return self.render_to_response(self.get_context_data(form=DiscoveryWatchEditForm(user=request.user, instance=watch), watch=watch))

    def post(self, request, *args, **kwargs):
        watch = self.get_watch()
        form = DiscoveryWatchEditForm(request.POST, user=request.user, instance=watch)
        if form.is_valid():
            form.save()
            messages.success(request, "Veille mise à jour.")
            return redirect("discovery:watch-detail", watch_id=watch.pk)
        return self.render_to_response(self.get_context_data(form=form, watch=watch), status=400)


class WatchStatusView(OwnedWatchMixin, View):
    def post(self, request, *args, **kwargs):
        watch = self.get_watch()
        action = request.POST.get("action")
        if action == "pause":
            watch.status = DiscoveryWatchStatus.PAUSED
            watch.save(update_fields=["status", "updated_at"])
            messages.info(request, "Veille mise en pause.")
        elif action == "activate":
            watch.status = DiscoveryWatchStatus.ACTIVE
            watch.save(update_fields=["status", "updated_at"])
            messages.success(request, "Veille réactivée.")
        else:
            messages.error(request, "Action de Veille invalide.")
        return redirect("discovery:watch-detail", watch_id=watch.pk)


class WatchDeleteView(OwnedWatchMixin, View):
    def post(self, request, *args, **kwargs):
        watch = self.get_watch()
        watch.delete()
        messages.info(request, "Veille supprimée.")
        return redirect("discovery:watch-list")
