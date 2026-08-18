from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, TemplateView, UpdateView

from events.permissions import user_can_manage_events
from events.selectors import get_manageable_events

from .forms import EventAccessGateForm, ScannerAssignmentForm
from .intelligence import event_access_snapshot
from .models import EventAccessGate, ScanResult, ScannerAssignment
from .permissions import (
    get_active_assignment,
    user_can_manage_scanner_assignments,
)
from .selectors import (
    get_access_gates_visible_to,
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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        assignment = get_active_assignment(self.request.user, self.object)
        context["assignment"] = assignment
        context["access_gates"] = EventAccessGate.objects.filter(
            event=self.object,
            is_active=True,
        ).order_by("priority", "name")
        context["assigned_gate"] = assignment.access_gate if assignment else None
        context["can_manage_access"] = user_can_manage_scanner_assignments(
            self.request.user,
            self.object,
        )
        return context


class ScannerWebScanView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, slug):
        event = get_object_or_404(get_scannable_events(request.user), slug=slug)
        token = request.POST.get("token", "")
        client_reference = request.POST.get("client_reference", "")
        gate = request.POST.get("gate", "")
        access_gate_id = request.POST.get("access_gate_id", "")
        access_gate = None
        if access_gate_id:
            access_gate = get_object_or_404(EventAccessGate, pk=access_gate_id, event=event)

        try:
            outcome = scan_ticket(
                token=token,
                actor=request.user,
                event=event,
                client_reference=client_reference,
                gate=gate,
                access_gate=access_gate,
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
            "gate": outcome.log.gate,
            "access_gate_id": str(outcome.log.access_gate_id) if outcome.log.access_gate_id else None,
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


class LiveAccessDashboardView(LoginRequiredMixin, DetailView):
    template_name = "scanner/live_access.html"
    context_object_name = "event"
    slug_field = "slug"
    slug_url_kwarg = "slug"
    login_url = "core:login"

    def get_queryset(self):
        return get_scannable_events(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["snapshot"] = event_access_snapshot(self.object)
        context["can_manage_access"] = user_can_manage_scanner_assignments(
            self.request.user,
            self.object,
        )
        return context


class LiveAccessSnapshotView(LoginRequiredMixin, View):
    login_url = "core:login"

    def get(self, request, slug):
        event = get_object_or_404(get_scannable_events(request.user), slug=slug)
        snapshot = event_access_snapshot(event)
        # DjangoJSONEncoder used by JsonResponse handles datetimes/Decimals.
        return JsonResponse(snapshot)


class ScanLogListView(LoginRequiredMixin, ListView):
    template_name = "scanner/log_list.html"
    context_object_name = "scan_logs"
    paginate_by = 50
    login_url = "core:login"

    def get_queryset(self):
        queryset = get_scan_logs_visible_to(self.request.user)
        event_slug = self.request.GET.get("event")
        result = self.request.GET.get("result")
        gate_id = self.request.GET.get("gate")
        if event_slug:
            queryset = queryset.filter(event__slug=event_slug)
        if result in ScanResult.values:
            queryset = queryset.filter(result=result)
        if gate_id:
            queryset = queryset.filter(access_gate_id=gate_id)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["scannable_events"] = get_scannable_events(self.request.user)
        context["result_choices"] = ScanResult.choices
        context["access_gates"] = get_access_gates_visible_to(self.request.user).filter(is_active=True)
        return context


class AccessGateListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    template_name = "scanner/gate_list.html"
    context_object_name = "gates"
    paginate_by = 40
    login_url = "core:login"

    def test_func(self):
        return self.request.user.is_staff or get_manageable_events(self.request.user).exists()

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            raise PermissionDenied("Vous n’avez pas le droit de gérer les portes d’accès.")
        return super().handle_no_permission()

    def get_queryset(self):
        if self.request.user.is_staff:
            return get_access_gates_visible_to(self.request.user)
        return get_access_gates_visible_to(self.request.user).filter(
            event__in=get_manageable_events(self.request.user)
        )


class AccessGateCreateView(LoginRequiredMixin, CreateView):
    model = EventAccessGate
    form_class = EventAccessGateForm
    template_name = "scanner/gate_form.html"
    login_url = "core:login"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        if not user_can_manage_scanner_assignments(self.request.user, form.cleaned_data["event"]):
            raise PermissionDenied("Vous ne pouvez pas créer de porte pour cet événement.")
        form.instance.created_by = self.request.user
        form.instance.full_clean()
        messages.success(self.request, "Porte d’accès créée.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("scanner:gates")


class AccessGateUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = EventAccessGate
    form_class = EventAccessGateForm
    template_name = "scanner/gate_form.html"
    login_url = "core:login"

    def get_queryset(self):
        return get_access_gates_visible_to(self.request.user)

    def test_func(self):
        gate = self.get_object()
        return user_can_manage_scanner_assignments(self.request.user, gate.event)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        if not user_can_manage_scanner_assignments(self.request.user, form.cleaned_data["event"]):
            raise PermissionDenied("Vous ne pouvez pas modifier cette porte.")
        form.instance.full_clean()
        messages.success(self.request, "Porte d’accès mise à jour.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("scanner:gates")


class ScannerAssignmentListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    template_name = "scanner/assignment_list.html"
    context_object_name = "assignments"
    paginate_by = 30
    login_url = "core:login"

    def test_func(self):
        return self.request.user.is_staff or get_manageable_events(self.request.user).exists()

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            raise PermissionDenied("Un rôle de gestion d’accès est requis.")
        return super().handle_no_permission()

    def get_queryset(self):
        queryset = get_assignments_visible_to(self.request.user)
        if self.request.user.is_staff:
            return queryset
        manageable_events = get_manageable_events(self.request.user)
        return queryset.filter(
            Q(event__in=manageable_events)
            | Q(activity__event_vertical__in=manageable_events)
        ).distinct()


class ScannerAssignmentCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = ScannerAssignment
    form_class = ScannerAssignmentForm
    template_name = "scanner/assignment_form.html"
    login_url = "core:login"

    def test_func(self):
        return self.request.user.is_staff or get_manageable_events(self.request.user).exists()

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
        queryset = get_assignments_visible_to(self.request.user)
        if self.request.user.is_staff:
            return queryset
        manageable_events = get_manageable_events(self.request.user)
        return queryset.filter(
            Q(event__in=manageable_events)
            | Q(activity__event_vertical__in=manageable_events)
        ).distinct()

    def test_func(self):
        assignment = self.get_object()
        if assignment.activity_id:
            event = getattr(assignment.activity, "event_vertical", None)
            return bool(event and user_can_manage_scanner_assignments(self.request.user, event))
        return bool(
            assignment.event_id
            and user_can_manage_scanner_assignments(self.request.user, assignment.event)
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
