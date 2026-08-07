from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils import timezone
from django.views.generic import TemplateView

from accounts.models import PermissionGroup, Role
from events.models import Event, EventStatus, EventVisibility
from events.permissions import user_can_manage_events


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "base/dashboard.html"
    login_url = "core:login"

    def get_event_queryset(self):
        user = self.request.user
        queryset = Event.objects.select_related("category", "venue", "organizer")

        if user.is_staff:
            return queryset

        if user_can_manage_events(user):
            return queryset.filter(organizer=user)

        return queryset.filter(
            status=EventStatus.PUBLISHED,
            visibility=EventVisibility.PUBLIC,
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        User = get_user_model()
        events = self.get_event_queryset()
        now = timezone.now()

        context.update(
            {
                "users_count": User.objects.count(),
                "verified_users_count": User.objects.filter(
                    is_verified=True
                ).count(),
                "roles_count": Role.objects.filter(is_active=True).count(),
                "permission_groups_count": PermissionGroup.objects.count(),
                "events_count": events.count(),
                "published_events_count": events.filter(
                    status=EventStatus.PUBLISHED
                ).count(),
                "upcoming_events_count": events.filter(start_at__gt=now).count(),
                "upcoming_events": events.filter(start_at__gt=now).order_by(
                    "start_at"
                )[:5],
                "can_create_event": user_can_manage_events(self.request.user),
            }
        )
        return context
