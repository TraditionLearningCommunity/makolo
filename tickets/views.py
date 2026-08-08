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

from events.permissions import user_can_manage_event, user_can_manage_events
from events.selectors import get_events_visible_to, get_manageable_events
from partners.services import attribute_order, get_session_referral

from .forms import TicketTypeForm
from .models import (
    Ticket,
    TicketOrder,
    TicketTransfer,
    TicketType,
    TicketWaitlistEntry,
    TransferStatus,
    WaitlistStatus,
)
from .permissions import user_can_access_order, user_can_access_ticket
from .selectors import (
    get_orders_visible_to,
    get_ticket_transfers_visible_to,
    get_tickets_visible_to,
    get_waitlist_entries_visible_to,
)
from .services import (
    accept_ticket_transfer,
    accept_waitlist_offer,
    cancel_order,
    cancel_ticket_transfer,
    can_join_waitlist,
    create_order,
    create_ticket_transfer,
    decline_ticket_transfer,
    join_waitlist,
    leave_waitlist,
)


class MyTicketListView(LoginRequiredMixin, ListView):
    model = Ticket
    template_name = "tickets/ticket_list.html"
    context_object_name = "tickets"
    paginate_by = 20
    login_url = "core:login"

    def get_queryset(self):
        return get_tickets_visible_to(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["incoming_transfer_count"] = get_ticket_transfers_visible_to(
            self.request.user
        ).filter(recipient=self.request.user, status=TransferStatus.PENDING).count()
        context["active_waitlist_count"] = get_waitlist_entries_visible_to(
            self.request.user
        ).filter(status__in=[WaitlistStatus.WAITING, WaitlistStatus.OFFERED]).count()
        return context


class TicketDetailView(LoginRequiredMixin, DetailView):
    model = Ticket
    template_name = "tickets/ticket_detail.html"
    context_object_name = "ticket"
    login_url = "core:login"

    def get_queryset(self):
        return get_tickets_visible_to(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["pending_transfer"] = self.object.transfers.filter(
            status=TransferStatus.PENDING
        ).select_related("recipient").first()
        context["can_transfer"] = bool(
            self.object.owner_id == self.request.user.pk and self.object.is_valid
        )
        return context


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
        return TicketType.objects.select_related("event").filter(
            event__in=get_manageable_events(self.request.user)
        ).order_by("event__start_at", "price", "name")


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
        return list(event.ticket_types.filter(is_active=True).order_by("price", "name"))

    def _context(self, request, event, ticket_types=None):
        ticket_types = ticket_types if ticket_types is not None else self._ticket_types(event)
        active_entries = TicketWaitlistEntry.objects.filter(
            user=request.user,
            ticket_type__in=ticket_types,
            status__in=[WaitlistStatus.WAITING, WaitlistStatus.OFFERED],
        )
        active_ids = set(active_entries.values_list("ticket_type_id", flat=True))
        eligible_ids = {
            ticket_type.pk
            for ticket_type in ticket_types
            if ticket_type.pk not in active_ids and can_join_waitlist(request.user, ticket_type)
        }
        referral = get_session_referral(request, event=event)
        return {
            "event": event,
            "ticket_types": ticket_types,
            "waitlist_eligible_ids": eligible_ids,
            "active_waitlist_type_ids": active_ids,
            "referral_partner": referral.partner.display_name if referral else "",
        }

    def get(self, request, event_slug):
        event = self._event(request, event_slug)
        return render(request, self.template_name, self._context(request, event))

    def post(self, request, event_slug):
        event = self._event(request, event_slug)
        ticket_types = self._ticket_types(event)
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
            attribute_order(order=order, request=request)
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
            return render(
                request,
                self.template_name,
                self._context(request, event, ticket_types),
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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["waitlist_entry"] = TicketWaitlistEntry.objects.filter(
            offered_order=self.object,
            user=self.request.user,
        ).first()
        return context


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


class WaitlistListView(LoginRequiredMixin, ListView):
    model = TicketWaitlistEntry
    template_name = "tickets/waitlist_list.html"
    context_object_name = "entries"
    login_url = "core:login"
    paginate_by = 30

    def get_queryset(self):
        return get_waitlist_entries_visible_to(self.request.user).order_by("-created_at")


class WaitlistJoinView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, ticket_type_id):
        ticket_type = get_object_or_404(
            TicketType.objects.select_related("event"),
            pk=ticket_type_id,
        )
        quantity = request.POST.get("quantity", "1")
        try:
            entry = join_waitlist(
                user=request.user,
                ticket_type=ticket_type,
                quantity=quantity,
            )
        except (ValidationError, PermissionDenied) as exc:
            messages.error(request, "; ".join(getattr(exc, "messages", [str(exc)])))
        else:
            messages.success(
                request,
                f"Vous êtes sur la liste d’attente pour {entry.ticket_type.name}. Makolo vous préviendra automatiquement dès qu’une place sera réservée pour vous.",
            )
        return redirect("tickets:order-create", event_slug=ticket_type.event.slug)


class WaitlistLeaveView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, pk):
        entry = get_object_or_404(get_waitlist_entries_visible_to(request.user), pk=pk)
        try:
            leave_waitlist(entry=entry, user=request.user)
        except (ValidationError, PermissionDenied) as exc:
            messages.error(request, "; ".join(getattr(exc, "messages", [str(exc)])))
        else:
            messages.success(request, "Vous avez quitté cette liste d’attente.")
        return redirect("tickets:waitlist-list")


class WaitlistAcceptView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, pk):
        entry = get_object_or_404(get_waitlist_entries_visible_to(request.user), pk=pk)
        try:
            order = accept_waitlist_offer(entry=entry, user=request.user)
        except (ValidationError, PermissionDenied) as exc:
            messages.error(request, "; ".join(getattr(exc, "messages", [str(exc)])))
            return redirect("tickets:waitlist-list")

        if order.total_amount > 0:
            messages.info(request, "Votre place est réservée. Finalisez le paiement avant l’expiration.")
        else:
            messages.success(request, "Offre acceptée : votre billet et son nouveau QR sont disponibles.")
        return redirect("tickets:order-detail", pk=order.pk)


class TransferListView(LoginRequiredMixin, ListView):
    model = TicketTransfer
    template_name = "tickets/transfer_list.html"
    context_object_name = "transfers"
    login_url = "core:login"
    paginate_by = 30

    def get_queryset(self):
        return get_ticket_transfers_visible_to(self.request.user).order_by("-created_at")


class TicketTransferCreateView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, pk):
        ticket = get_object_or_404(Ticket.objects.select_related("event", "owner"), pk=pk)
        try:
            transfer = create_ticket_transfer(
                ticket=ticket,
                sender=request.user,
                recipient_email=request.POST.get("recipient_email", ""),
            )
        except (ValidationError, PermissionDenied) as exc:
            messages.error(request, "; ".join(getattr(exc, "messages", [str(exc)])))
        else:
            messages.success(
                request,
                f"Transfert sécurisé envoyé à {transfer.recipient_email}. Le destinataire doit l’accepter dans Makolo.",
            )
        return redirect("tickets:detail", pk=ticket.pk)


class TicketTransferAcceptView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, pk):
        transfer = get_object_or_404(get_ticket_transfers_visible_to(request.user), pk=pk)
        try:
            accept_ticket_transfer(transfer=transfer, recipient=request.user)
        except (ValidationError, PermissionDenied) as exc:
            messages.error(request, "; ".join(getattr(exc, "messages", [str(exc)])))
        else:
            messages.success(
                request,
                "Transfert accepté. L’ancien QR code a été invalidé et votre nouveau QR est prêt.",
            )
        return redirect("tickets:transfer-list")


class TicketTransferDeclineView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, pk):
        transfer = get_object_or_404(get_ticket_transfers_visible_to(request.user), pk=pk)
        try:
            decline_ticket_transfer(transfer=transfer, recipient=request.user)
        except (ValidationError, PermissionDenied) as exc:
            messages.error(request, "; ".join(getattr(exc, "messages", [str(exc)])))
        else:
            messages.success(request, "Transfert refusé.")
        return redirect("tickets:transfer-list")


class TicketTransferCancelView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, pk):
        transfer = get_object_or_404(get_ticket_transfers_visible_to(request.user), pk=pk)
        try:
            cancel_ticket_transfer(transfer=transfer, sender=request.user)
        except (ValidationError, PermissionDenied) as exc:
            messages.error(request, "; ".join(getattr(exc, "messages", [str(exc)])))
        else:
            messages.success(request, "Transfert annulé.")
        return redirect("tickets:transfer-list")
