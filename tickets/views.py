from io import BytesIO

import qrcode
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from events.models import Event
from events.permissions import user_can_manage_event, user_can_manage_events
from events.selectors import get_events_visible_to

from .forms import TicketTypeForm
from .models import Ticket, TicketOrder, TicketType
from .permissions import user_can_access_order, user_can_access_ticket
from .selectors import get_orders_visible_to, get_tickets_visible_to
from .services import cancel_order, create_order


class MyTicketListView(LoginRequiredMixin, ListView):
    model = Ticket
    template_name = "tickets/ticket_list.html"
    context_object_name = "tickets"
    paginate_by = 20
    login_url = "core:login"

    def get_queryset(self):
        return get_tickets_visible_to(self.request.user)


class TicketDetailView(LoginRequiredMixin, DetailView):
    model = Ticket
    template_name = "tickets/ticket_detail.html"
    context_object_name = "ticket"
    login_url = "core:login"

    def get_queryset(self):
        return get_tickets_visible_to(self.request.user)


class TicketQrView(LoginRequiredMixin, View):
    login_url = "core:login"

    def get(self, request, pk):
        ticket = get_object_or_404(
            Ticket.objects.select_related("event", "ticket_type", "owner"),
            pk=pk,
        )
        if not user_can_access_ticket(request.user, ticket):
            raise PermissionDenied

        image = qrcode.make(ticket.qr_token)
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        return HttpResponse(buffer.getvalue(), content_type="image/png")


class TicketTypeListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = TicketType
    template_name = "tickets/ticket_type_list.html"
    context_object_name = "ticket_types"
    login_url = "core:login"

    def test_func(self):
        return user_can_manage_events(self.request.user)

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            raise PermissionDenied("Un rôle organisateur est requis.")
        return super().handle_no_permission()

    def get_queryset(self):
        queryset = TicketType.objects.select_related("event").order_by(
            "event__start_at", "price", "name"
        )
        if self.request.user.is_staff:
            return queryset
        return queryset.filter(event__organizer=self.request.user)


class TicketTypeCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = TicketType
    form_class = TicketTypeForm
    template_name = "tickets/ticket_type_form.html"
    login_url = "core:login"

    def test_func(self):
        return user_can_manage_events(self.request.user)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        if not user_can_manage_event(self.request.user, form.cleaned_data["event"]):
            raise PermissionDenied
        form.instance.full_clean()
        messages.success(self.request, "Type de billet créé.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("tickets:manage-types")


class TicketTypeUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = TicketType
    form_class = TicketTypeForm
    template_name = "tickets/ticket_type_form.html"
    login_url = "core:login"

    def test_func(self):
        return user_can_manage_event(self.request.user, self.get_object().event)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.instance.full_clean()
        messages.success(self.request, "Type de billet mis à jour.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("tickets:manage-types")


class EventTicketOrderView(LoginRequiredMixin, View):
    login_url = "core:login"
    template_name = "tickets/order_form.html"

    def _event(self, request, slug):
        return get_object_or_404(
            get_events_visible_to(request.user, for_detail=True),
            slug=slug,
        )

    def _ticket_types(self, event):
        return event.ticket_types.filter(is_active=True).order_by("price", "name")

    def get(self, request, event_slug):
        event = self._event(request, event_slug)
        return render(
            request,
            self.template_name,
            {"event": event, "ticket_types": self._ticket_types(event)},
        )

    def post(self, request, event_slug):
        event = self._event(request, event_slug)
        ticket_types = list(self._ticket_types(event))
        selections = []
        for ticket_type in ticket_types:
            raw = request.POST.get(f"quantity_{ticket_type.pk}", "0")
            try:
                quantity = int(raw or 0)
            except ValueError:
                quantity = 0
            if quantity > 0:
                selections.append((ticket_type, quantity))

        customer_name = (
            request.POST.get("customer_name")
            or request.user.full_name
            or request.user.username
        )
        customer_email = request.POST.get("customer_email") or request.user.email

        try:
            order = create_order(
                buyer=request.user,
                event=event,
                customer_name=customer_name,
                customer_email=customer_email,
                selections=selections,
            )
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
            return render(
                request,
                self.template_name,
                {"event": event, "ticket_types": ticket_types},
                status=400,
            )

        if order.status == "confirmed":
            messages.success(request, "Billets gratuits émis avec succès.")
        else:
            messages.success(
                request,
                "Commande réservée. Le paiement devra être confirmé avant expiration.",
            )
        return redirect("tickets:order-detail", pk=order.pk)


class TicketOrderDetailView(LoginRequiredMixin, DetailView):
    model = TicketOrder
    template_name = "tickets/order_detail.html"
    context_object_name = "order"
    login_url = "core:login"

    def get_queryset(self):
        return get_orders_visible_to(self.request.user)


class TicketOrderCancelView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, pk):
        order = get_object_or_404(get_orders_visible_to(request.user), pk=pk)
        if not user_can_access_order(request.user, order):
            raise PermissionDenied
        try:
            cancel_order(order=order, actor=request.user)
        except (ValidationError, PermissionDenied) as exc:
            messages.error(request, "; ".join(getattr(exc, "messages", [str(exc)])))
        else:
            messages.success(request, "Commande annulée.")
        return redirect("tickets:order-detail", pk=order.pk)
