from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404
from django.views import View
from django.views.generic import TemplateView

from access.services import resolve_access_credential, validate_access
from activities.models import Activity
from authorization.constants import PermissionCode
from authorization.services import can

from .console_views import SpaceConsoleMixin


class SpaceActivityScannerView(SpaceConsoleMixin, TemplateView):
    template_name = "organizations/console/scanner.html"
    module_key = "control"
    page_title = "Scanner"

    def get_activity(self):
        queryset = Activity.objects.filter(space=self.space)
        if self.space_console.activity_ids is not None:
            queryset = queryset.filter(pk__in=self.space_console.activity_ids)
        activity = get_object_or_404(queryset, pk=self.kwargs["activity_id"])
        if not can(self.request.user, PermissionCode.ACTIVITY_ACCESS_SCAN, activity=activity):
            raise PermissionDenied("Votre Mandat ne permet pas de contrôler les accès de cette Activity.")
        return activity

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        activity = self.get_activity()
        context["activity"] = activity
        context["console_page_title"] = f"Contrôle · {activity.title}"
        context["occurrences"] = activity.occurrences.order_by("start_at", "id")
        return context

    def post(self, request, *args, **kwargs):
        activity = self.get_activity()
        token = (request.POST.get("token") or "").strip()
        occurrence = None
        occurrence_id = (request.POST.get("occurrence") or "").strip()
        if occurrence_id:
            occurrence = get_object_or_404(activity.occurrences.all(), pk=occurrence_id)
        try:
            credential = resolve_access_credential(token)
            outcome = validate_access(
                access=credential.access,
                credential=credential,
                controller=request.user,
                authority_check=lambda actor, access: can(
                    actor,
                    PermissionCode.ACTIVITY_ACCESS_SCAN,
                    activity=access.activity,
                ),
                expected_activity=activity,
                expected_occurrence=occurrence,
                source="space_console",
            )
        except ValidationError as exc:
            outcome = None
            error_message = "; ".join(exc.messages)
        else:
            error_message = ""
        context = self.get_context_data(**kwargs)
        context["scan_outcome"] = outcome
        context["scan_error"] = error_message
        return self.render_to_response(context)
