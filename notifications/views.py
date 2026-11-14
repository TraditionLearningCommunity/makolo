from django.urls import reverse
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views import View
from django.views.generic import ListView

from accounts.models import NotificationPreference
from core.participant_selectors import participant_accesses, participant_journeys, participant_orders
from core.web_navigation import safe_post_next

from .forms import NotificationPreferenceForm
from .navigation import build_notification_navigation
from .selectors import get_notifications_for_user
from .visuals import notification_visual


class NotificationListView(LoginRequiredMixin, ListView):
    template_name = "notifications/notification_list.html"
    context_object_name = "notifications"
    paginate_by = None
    login_url = "core:login"

    def get_queryset(self):
        queryset = get_notifications_for_user(self.request.user).select_related(
            "activity", "activity__event_vertical", "journey", "journey__activity",
            "journey__activity__event_vertical",
        )
        if self.request.GET.get("filter") == "unread":
            queryset = queryset.filter(read_at__isnull=True)
        return queryset.order_by('-created_at', '-id')[:15]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_filter"] = self.request.GET.get("filter", "all")
        owner_queryset = get_notifications_for_user(self.request.user)
        context["total_count"] = owner_queryset.count()
        context["unread_count"] = owner_queryset.filter(read_at__isnull=True).count()
        notifications = list(context["notifications"])
        for notification in notifications:
            notification.visual = notification_visual(notification, self.request)
            navigation = build_notification_navigation(notification)
            local_action = (
                notification.action_url.startswith("/")
                and not notification.action_url.startswith("//")
                and "\\" not in notification.action_url
            )
            notification.can_open = bool(
                local_action
                or notification.access_id
                or notification.journey_id
                or notification.activity_id
                or notification.commerce_order_id
                or (navigation and navigation["target"] in {
                    "conversation", "journey", "access", "occurrence",
                })
            )
        context["notifications"] = notifications
        return context


class NotificationOpenView(LoginRequiredMixin, View):
    login_url = "core:login"

    def get(self, request, pk):
        notification = get_object_or_404(get_notifications_for_user(request.user), pk=pk)
        notification.mark_read()

        if notification.access_id:
            access = participant_accesses(request.user).filter(pk=notification.access_id).first()
            if access:
                return redirect("core:participant-access-detail", pk=access.pk)
            return redirect("notifications:list")

        if notification.template_key == "journey.payment.required" and notification.commerce_order_id:
            order = participant_orders(request.user).filter(pk=notification.commerce_order_id).first()
            if order:
                return redirect("payments:commerce-start", order_pk=order.pk)
            return redirect("notifications:list")

        if notification.journey_id:
            journey = participant_journeys(request.user).filter(pk=notification.journey_id).first()
            if journey:
                return redirect("core:participant-journey-detail", pk=journey.pk)
            return redirect("notifications:list")

        if notification.activity_id:
            journey = (
                participant_journeys(request.user)
                .filter(activity_id=notification.activity_id)
                .order_by("-created_at")
                .first()
            )
            if journey:
                return redirect("core:participant-journey-detail", pk=journey.pk)
            access = (
                participant_accesses(request.user)
                .filter(activity_id=notification.activity_id)
                .order_by("-created_at")
                .first()
            )
            if access:
                return redirect("core:participant-access-detail", pk=access.pk)

        # Structured notifications can carry a real owner even without an action_url.
        # The owner endpoint still enforces current access and visibility.
        navigation = build_notification_navigation(notification)
        if navigation:
            target = navigation["target"]
            resource_id = navigation["resource"]["id"]
            try:
                from uuid import UUID

                UUID(resource_id)
            except (ValueError, TypeError, AttributeError):
                resource_id = None
            if resource_id and target == "conversation":
                point_id = navigation.get("point_id")
                if point_id:
                    try:
                        UUID(str(point_id))
                    except (ValueError, TypeError, AttributeError):
                        point_id = None
                if point_id:
                    return redirect(
                        f"{reverse('conversations:detail', kwargs={'pk': resource_id})}"
                        f"?focus={point_id}#point-{point_id}"
                    )
                return redirect("conversations:detail", pk=resource_id)
            if resource_id and target == "access":
                access = participant_accesses(request.user).filter(pk=resource_id).first()
                if access:
                    return redirect("core:participant-access-detail", pk=access.pk)
            if resource_id and target == "journey":
                journey = participant_journeys(request.user).filter(pk=resource_id).first()
                if journey:
                    return redirect("core:participant-journey-detail", pk=journey.pk)
            if resource_id and target == "occurrence":
                journey = (
                    participant_journeys(request.user)
                    .filter(occurrence_id=resource_id)
                    .order_by("-created_at").first()
                )
                if journey:
                    return redirect("core:participant-journey-detail", pk=journey.pk)

        if (
            notification.action_url.startswith("/")
            and not notification.action_url.startswith("//")
            and "\\" not in notification.action_url
        ):
            return redirect(notification.action_url)
        return redirect("notifications:list")


class NotificationMarkReadView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request, pk):
        notification = get_object_or_404(get_notifications_for_user(request.user), pk=pk)
        notification.mark_read()
        return redirect(safe_post_next(request, fallback="notifications:list"))


class NotificationMarkAllReadView(LoginRequiredMixin, View):
    login_url = "core:login"

    def post(self, request):
        now = timezone.now()
        get_notifications_for_user(request.user).filter(read_at__isnull=True).update(
            read_at=now,
            updated_at=now,
        )
        messages.success(request, "Toutes les notifications ont été marquées comme lues.")
        return redirect("notifications:list")


class NotificationPreferenceView(LoginRequiredMixin, View):
    template_name = "notifications/preferences.html"
    login_url = "core:login"

    def get_object(self, request):
        try:
            return request.user.notification_preferences
        except NotificationPreference.DoesNotExist:
            return NotificationPreference(user=request.user)

    def get(self, request):
        form = NotificationPreferenceForm(instance=self.get_object(request))
        return render(request, self.template_name, {"form": form})

    def post(self, request):
        preference = self.get_object(request)
        form = NotificationPreferenceForm(request.POST, instance=preference)
        if form.is_valid():
            form.save()
            messages.success(request, "Préférences de notification enregistrées.")
            return redirect("notifications:preferences")
        return render(request, self.template_name, {"form": form}, status=400)
