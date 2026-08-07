from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from .forms import EventForm
from .models import Event
from .permissions import user_can_manage_event, user_can_manage_events
from .selectors import get_manageable_events
from .services import cancel_event, complete_event, publish_event


class EventListView(LoginRequiredMixin, ListView):
    model = Event
    template_name = "events/event_list.html"
    context_object_name = "events"
    paginate_by = 20
    login_url = "core:login"

    def get_queryset(self):
        return get_manageable_events(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["can_create_event"] = user_can_manage_events(self.request.user)
        return context


class EventCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Event
    form_class = EventForm
    template_name = "events/event_form.html"
    login_url = "core:login"

    def test_func(self):
        return user_can_manage_events(self.request.user)

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            raise PermissionDenied("Un rôle organisateur est requis.")
        return super().handle_no_permission()

    def form_valid(self, form):
        form.instance.organizer = self.request.user
        messages.success(self.request, "Événement créé en brouillon.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("events:detail", kwargs={"slug": self.object.slug})


class EventDetailView(LoginRequiredMixin, DetailView):
    model = Event
    template_name = "events/event_detail.html"
    context_object_name = "event"
    slug_field = "slug"
    slug_url_kwarg = "slug"
    login_url = "core:login"

    def get_queryset(self):
        return get_manageable_events(self.request.user)


class EventUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Event
    form_class = EventForm
    template_name = "events/event_form.html"
    slug_field = "slug"
    slug_url_kwarg = "slug"
    login_url = "core:login"

    def get_queryset(self):
        return get_manageable_events(self.request.user)

    def test_func(self):
        event = self.get_object()
        return user_can_manage_event(self.request.user, event)

    def form_valid(self, form):
        messages.success(self.request, "Événement mis à jour.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("events:detail", kwargs={"slug": self.object.slug})


class EventTransitionView(LoginRequiredMixin, View):
    service = None
    success_message = "Événement mis à jour."
    login_url = "core:login"

    def post(self, request, slug):
        event = get_object_or_404(get_manageable_events(request.user), slug=slug)
        try:
            self.service(event=event, actor=request.user)
        except (ValidationError, PermissionDenied) as exc:
            message = "; ".join(getattr(exc, "messages", [str(exc)]))
            messages.error(request, message)
        else:
            messages.success(request, self.success_message)
        return redirect("events:detail", slug=event.slug)


class EventPublishView(EventTransitionView):
    service = staticmethod(publish_event)
    success_message = "Événement publié."


class EventCancelView(EventTransitionView):
    service = staticmethod(cancel_event)
    success_message = "Événement annulé."


class EventCompleteView(EventTransitionView):
    service = staticmethod(complete_event)
    success_message = "Événement marqué comme terminé."
