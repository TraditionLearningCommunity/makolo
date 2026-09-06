from datetime import datetime

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from activities.models import OccurrenceScheduleFrequency, OccurrenceStatus, OccurrenceTimingKind
from automation.services import ensure_policy
from core.participant_presentation import resolve_participant_activity_state
from core.participant_selectors import participant_state_context
from discovery.presentation import availability_presentation, presenter_for, price_presentation

from .forms import EventForm
from .models import Event, EventStatus
from .permissions import user_can_manage_event, user_can_manage_events
from .selectors import get_events_visible_to, get_manageable_events
from .services import (
    cancel_event,
    complete_event,
    create_event,
    create_event_schedule,
    publish_event,
    reopen_event,
    update_event,
)


SCHEDULE_FORM_KEYS = {"repeat", "frequency", "interval", "weekdays", "repeat_until"}


def _schedule_duration_minutes(values):
    if values.get("timing_kind") != OccurrenceTimingKind.EXACT:
        return None
    start_date = values.get("start_date")
    start_time = values.get("start_time")
    end_time = values.get("end_time")
    if not start_date or not start_time or not end_time:
        return None
    end_date = values.get("end_date") or start_date
    minutes = int((datetime.combine(end_date, end_time) - datetime.combine(start_date, start_time)).total_seconds() // 60)
    return minutes if minutes > 0 else None


def _pop_schedule_values(values):
    return {key: values.pop(key, None) for key in SCHEDULE_FORM_KEYS}


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
            raise PermissionDenied("Vous ne pouvez pas créer cet événement.")
        return super().handle_no_permission()

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        values = dict(form.cleaned_data)
        schedule_values = _pop_schedule_values(values)
        if schedule_values["repeat"]:
            # The durable Event is created first; the recurrence then materializes
            # concrete Occurrences through the generic Activities schedule service.
            occurrence_values = {
                key: values.pop(key, None)
                for key in ("start_at", "end_at", "start_date", "start_time", "end_date", "end_time", "timing_kind", "timezone")
            }
            self.object = create_event(actor=self.request.user, **values)
            start_date = occurrence_values["start_date"]
            frequency = schedule_values["frequency"]
            month_day = start_date.day if frequency in {OccurrenceScheduleFrequency.MONTHLY, OccurrenceScheduleFrequency.YEARLY} else None
            month = start_date.month if frequency == OccurrenceScheduleFrequency.YEARLY else None
            create_event_schedule(
                event=self.object,
                actor=self.request.user,
                frequency=frequency,
                starts_on=start_date,
                ends_on=schedule_values["repeat_until"],
                materialize_through=schedule_values["repeat_until"],
                timezone_name=occurrence_values["timezone"],
                interval=schedule_values["interval"] or 1,
                timing_kind=occurrence_values["timing_kind"],
                start_time=occurrence_values["start_time"],
                duration_minutes=_schedule_duration_minutes(occurrence_values),
                weekdays=tuple(int(day) for day in (schedule_values["weekdays"] or ())),
                month_day=month_day,
                month=month,
                venue=self.object.venue,
            )
        else:
            values["start_at"] = values.get("start_at") or None
            values["end_at"] = values.get("end_at") or None
            self.object = create_event(actor=self.request.user, **values)
        ensure_policy(self.object)
        messages.success(self.request, "Événement créé en brouillon avec ses dates Makolo.")
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
        can_manage_event = user_can_manage_event(self.request.user, self.object)
        context["can_manage_event"] = can_manage_event
        occurrences = list(self.object.activity.occurrences.order_by("start_date", "start_time", "id"))
        context["event_occurrences"] = occurrences
        future_completed = [row for row in occurrences if row.status == OccurrenceStatus.COMPLETED and row.is_future]
        context["can_reopen_event"] = bool(can_manage_event and self.object.status == EventStatus.COMPLETED and future_completed)
        context["is_bookmarked"] = False
        context["can_submit_feedback"] = False

        selected = None
        requested_occurrence = self.request.GET.get("occurrence")
        if requested_occurrence:
            selected = next((row for row in occurrences if str(row.pk) == requested_occurrence), None)
        viable = [row for row in occurrences if row.status == OccurrenceStatus.SCHEDULED]
        if selected is None and len(viable) == 1:
            selected = viable[0]
        context["selected_occurrence"] = selected
        context["participant_presentation"] = None
        context["requires_occurrence_selection"] = bool(len(viable) > 1 and selected is None)

        if selected is not None:
            now = timezone.now()
            availability = availability_presentation(selected, now=now)
            price = price_presentation(selected, now=now)
            presenter = presenter_for(selected)
            public_cta = presenter.cta(selected, price=price, availability=availability)
            acquisition_url = None
            if (
                self.object.status == EventStatus.PUBLISHED
                and self.object.is_registration_open
                and availability.state != "sold_out"
                and public_cta != "Voir l’événement"
                and selected.start_at is not None
            ):
                base_url = reverse("tickets:order-create", kwargs={"event_slug": self.object.slug})
                acquisition_url = f"{base_url}?occurrence={selected.pk}"
            participant_context = participant_state_context(self.request.user, [selected])
            context["participant_presentation"] = resolve_participant_activity_state(
                profile=self.request.user,
                activity=self.object.activity,
                occurrence=selected,
                context=participant_context,
                availability_state=availability.state,
                availability_label=availability.label,
                acquisition_label=public_cta if acquisition_url else None,
                acquisition_url=acquisition_url,
                detail_url=reverse("events:detail", kwargs={"slug": self.object.slug}),
                now=now,
            )

        if self.request.user.is_authenticated:
            from discovery.models import ActivityBookmark
            from growth.models import EventFeedback
            from growth.services import can_submit_feedback

            context["is_bookmarked"] = ActivityBookmark.objects.filter(user=self.request.user, activity=self.object.activity).exists()
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
        values = dict(form.cleaned_data)
        _pop_schedule_values(values)
        self.object = update_event(
            event=self.object,
            actor=self.request.user,
            organization=values.pop("organization", None),
            **values,
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


class EventReopenView(EventTransitionView):
    service = staticmethod(reopen_event)
    success_message = "Événement réouvert."
