from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils import timezone
from django.views.generic import TemplateView

from events.models import Event, EventStatus, EventVisibility
from events.permissions import user_can_manage_events
from events.selectors import get_manageable_events
from payments.models import PaymentStatus
from payments.selectors import get_payments_visible_to
from tickets.models import TicketOrderStatus, TicketStatus
from tickets.selectors import get_orders_visible_to, get_tickets_visible_to


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "base/dashboard.html"
    login_url = "core:login"

    def get_event_queryset(self):
        user = self.request.user
        if user.is_staff:
            return Event.objects.select_related("category", "venue", "organizer", "organization")

        if user_can_manage_events(user):
            return get_manageable_events(user)

        # Participants and non-event organization roles get public discovery
        # here; their private financial/access data comes from capability-aware
        # selectors below rather than from organization membership in general.
        return Event.objects.select_related("category", "venue", "organizer", "organization").filter(
            status=EventStatus.PUBLISHED,
            visibility=EventVisibility.PUBLIC,
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        events = self.get_event_queryset()
        tickets = get_tickets_visible_to(self.request.user)
        orders = get_orders_visible_to(self.request.user)
        payments = get_payments_visible_to(self.request.user)
        now = timezone.now()

        context.update(
            {
                "events_count": events.count(),
                "published_events_count": events.filter(
                    status=EventStatus.PUBLISHED
                ).count(),
                "upcoming_events_count": events.filter(start_at__gt=now).count(),
                "upcoming_events": events.filter(start_at__gt=now).order_by(
                    "start_at"
                )[:5],
                "tickets_count": tickets.count(),
                "valid_tickets_count": tickets.filter(
                    status=TicketStatus.VALID
                ).count(),
                "pending_orders_count": orders.filter(
                    status=TicketOrderStatus.PENDING
                ).count(),
                "confirmed_orders_count": orders.filter(
                    status=TicketOrderStatus.CONFIRMED
                ).count(),
                "payments_count": payments.count(),
                "pending_payments_count": payments.filter(
                    status=PaymentStatus.PENDING
                ).count(),
                "succeeded_payments_count": payments.filter(
                    status=PaymentStatus.SUCCEEDED
                ).count(),
                "refunded_payments_count": payments.filter(
                    status=PaymentStatus.REFUNDED
                ).count(),
                "can_create_event": user_can_manage_events(self.request.user),
            }
        )
        return context
