from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, TemplateView, UpdateView

from events.permissions import user_can_manage_events

from .forms import ScannerAssignmentForm
from .models import ScanResult, ScannerAssignment
from .permissions import user_can_manage_scanner_assignments
from .selectors import (
    get_assignments_visible_to,
    get_scan_logs_visible_to,
    get_scannable_events,
)
from .services import scan_ticket


class ScannerHomeView(LoginRequiredMixin, TemplateView):
    template_name = "scanner/home.html"
    login_url = "core:login"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["scannable_events"] = get_scannable_events(self.request.user).order_by(
            "start_at", "title"
        )
        context["can_manage_assignments"] = user_can_manage_events(self.request.user)
        return context


class ScannerEventConsoleView(LoginRequiredMixin, DetailView):
    template_name = "scanner/console.html"
    context_object_name = "event"
    slug_field = "slug"
    slug_url_kwarg = "slug"
    login_url = "core:login"

    def get_queryset(self):
        return get_scannable_events(self.request.user)


class ScannerWebScanView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, slug):
        event = get_object_or_404(get_scannable_events(request.user), slug=slug)
        token = request.POST.get("token", "")
        client_reference = request.POST.get("client_reference", "")
        gate = request.POST.get("gate", "")

        try:
            outcome = scan_ticket(
                token=token,
                actor=request.user,
                event=event,
                client_reference=client_reference,
                gate=gate,
                metadata={
                    "source": "web",
                    "user_agent": request.META.get("HTTP_USER_AGENT", "")[:250],
                },
            )
        except PermissionDenied as exc:
            return JsonResponse({"detail": str(exc)}, status=403)
        except ValidationError as exc:
            return JsonResponse({"detail": "; ".join(exc.messages)}, status=400)

        payload = {
            "accepted": outcome.accepted,
            "result": outcome.result,
            "message": outcome.message,
            "scan_id": str(outcome.log.pk),
            "scanned_at": outcome.log.scanned_at.isoformat(),
        }
        if outcome.ticket:
            payload["ticket"] = {
                "id": str(outcome.ticket.pk),
                "code": str(outcome.ticket.code),
                "holder_name": outcome.ticket.holder_name,
                "holder_email": outcome.ticket.holder_email,
                "ticket_type": outcome.ticket.ticket_type.name,
                "status": outcome.ticket.status,
            }
        return JsonResponse(payload, status=200)


class ScanLogListView(LoginRequiredMixin, ListView):
    template_name = "scanner/log_list.html"
    context_object_name = "scan_logs"
    paginate_by = 50
    login_url = "core:login"

    def get_queryset(self):
        queryset = get_scan_logs_visible_to(self.request.user)
        event_slug = self.request.GET.get("event")
        result = self.request.GET.get("result")
        if event_slug:
            queryset = queryset.filter(event__slug=event_slug)
        if result in ScanResult.values:
            queryset = queryset.filter(result=result)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["scannable_events"] = get_scannable_events(self.request.user)
        context["result_choices"] = ScanResult.choices
        return context


class ScannerAssignmentListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    template_name = "scanner/assignment_list.html"
    context_object_name = "assignments"
    paginate_by = 30
    login_url = "core:login"

    def test_func(self):
        return user_can_manage_events(self.request.user)

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            raise PermissionDenied("Un rôle organisateur est requis.")
        return super().handle_no_permission()

    def get_queryset(self):
        return get_assignments_visible_to(self.request.user).filter(
            event__organizer=self.request.user
        ) if not self.request.user.is_staff else get_assignments_visible_to(self.request.user)


class ScannerAssignmentCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = ScannerAssignment
    form_class = ScannerAssignmentForm
    template_name = "scanner/assignment_form.html"
    login_url = "core:login"

    def test_func(self):
        return user_can_manage_events(self.request.user)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        if not user_can_manage_scanner_assignments(
            self.request.user,
            form.cleaned_data["event"],
        ):
            raise PermissionDenied
        form.instance.assigned_by = self.request.user
        form.instance.full_clean()
        messages.success(self.request, "Agent scanner affecté.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("scanner:assignments")


class ScannerAssignmentUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = ScannerAssignment
    form_class = ScannerAssignmentForm
    template_name = "scanner/assignment_form.html"
    login_url = "core:login"

    def get_queryset(self):
        queryset = ScannerAssignment.objects.select_related("event", "agent")
        if self.request.user.is_staff:
            return queryset
        return queryset.filter(event__organizer=self.request.user)

    def test_func(self):
        assignment = self.get_object()
        return user_can_manage_scanner_assignments(
            self.request.user,
            assignment.event,
        )

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        if not user_can_manage_scanner_assignments(
            self.request.user,
            form.cleaned_data["event"],
        ):
            raise PermissionDenied
        form.instance.full_clean()
        messages.success(self.request, "Affectation scanner mise à jour.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("scanner:assignments")
