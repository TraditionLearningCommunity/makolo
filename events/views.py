from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from automation.services import ensure_policy
from organizations.models import OrganizationMembership
from organizations.services import ensure_personal_organization

from .forms import EventForm
from .models import Event
from .permissions import user_can_manage_event, user_can_manage_events
from .selectors import get_events_visible_to, get_manageable_events
from .services import cancel_event, complete_event, create_event, publish_event, update_event


class EventListView(ListView):
    model = Event
    template_name = "events/event_list.html"
    context_object_name = "events"
    paginate_by = 20

    def get_queryset(self):
        return get_events_visible_to(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["can_create_event"] = user_can_manage_events(self.request.user)
        context["has_organization"] = bool(
            self.request.user.is_authenticated
            and OrganizationMembership.objects.filter(user=self.request.user, is_active=True).exists()
        )
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
            raise PermissionDenied("Créez une organisation ou rejoignez une équipe ayant le droit de gérer les événements.")
        return super().handle_no_permission()

    def dispatch(self, request, *args, **kwargs):
        if (
            request.user.is_authenticated
            and user_can_manage_events(request.user)
            and not OrganizationMembership.objects.filter(user=request.user, is_active=True).exists()
        ):
            ensure_personal_organization(request.user)
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        self.object = create_event(actor=self.request.user, **form.cleaned_data)
        ensure_policy(self.object)
        messages.success(self.request, "Événement créé en brouillon avec Makolo Autopilot prêt à être configuré.")
        return redirect(self.get_success_url())

    def get_success_url(self):
        return reverse("events:detail", kwargs={"slug": self.object.slug})


class EventDetailView(DetailView):
    model = Event
    template_name = "events/event_detail.html"
    context_object_name = "event"
    slug_field = "slug"
    slug_url_kwarg = "slug"

    def get_queryset(self):
        return get_events_visible_to(self.request.user, for_detail=True)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["can_manage_event"] = user_can_manage_event(self.request.user, self.object)
        context["is_bookmarked"] = False
        context["can_submit_feedback"] = False
        if self.request.user.is_authenticated:
            from discovery.models import EventBookmark
            from growth.models import EventFeedback
            from growth.services import can_submit_feedback

            context["is_bookmarked"] = EventBookmark.objects.filter(user=self.request.user, event=self.object).exists()
            context["can_submit_feedback"] = can_submit_feedback(self.request.user, self.object)
            context["existing_feedback"] = EventFeedback.objects.filter(user=self.request.user, event=self.object).first()
        return context


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
        return user_can_manage_event(self.request.user, self.get_object())

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        self.object = update_event(
            event=self.object,
            actor=self.request.user,
            organization=form.cleaned_data.pop("organization"),
            **form.cleaned_data,
        )
        messages.success(self.request, "Événement mis à jour.")
        return redirect(self.get_success_url())

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
            messages.error(request, "; ".join(getattr(exc, "messages", [str(exc)])))
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
