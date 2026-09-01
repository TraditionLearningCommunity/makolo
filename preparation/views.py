from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import TemplateView

from activities.models import Activity, Occurrence
from authorization.constants import PermissionCode
from authorization.services import can

from .models import ActivityResource, ResourceKind, ResourceVisibility
from .services import can_view_resource, create_resource, publish_resource, replace_resource


class ResourceDownloadView(View):
    def get(self, request, resource_id):
        resource = get_object_or_404(ActivityResource.objects.select_related("activity", "occurrence"), pk=resource_id)
        if resource.kind != ResourceKind.FILE or not resource.file or not can_view_resource(request.user, resource):
            raise Http404
        handle = resource.file.open("rb")
        response = FileResponse(handle, content_type=resource.mime_type or "application/octet-stream")
        response["Content-Disposition"] = f'attachment; filename="resource-{resource.pk}.bin"'
        response["X-Content-Type-Options"] = "nosniff"
        return response


class ManageResourcesView(LoginRequiredMixin, TemplateView):
    template_name = "preparation/manage.html"
    login_url = "core:login"

    def _activity(self):
        activity = get_object_or_404(Activity, pk=self.kwargs["activity_id"])
        if not can(self.request.user, PermissionCode.ACTIVITY_MANAGE, activity=activity):
            raise PermissionDenied("La gestion des Resources n’est pas autorisée.")
        return activity

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        activity = self._activity()
        resources = ActivityResource.objects.filter(activity=activity).select_related("occurrence", "supersedes").order_by("key", "version")
        context.update({"activity": activity, "resources": resources, "occurrences": activity.occurrences.all()})
        return context

    def post(self, request, *args, **kwargs):
        activity = self._activity()
        action = request.POST.get("action")
        try:
            if action == "create":
                occurrence = None
                occurrence_id = request.POST.get("occurrence_id")
                if occurrence_id:
                    occurrence = get_object_or_404(Occurrence, pk=occurrence_id, activity=activity)
                resource = create_resource(
                    activity=activity,
                    actor=request.user,
                    key=request.POST.get("key", ""),
                    title=request.POST.get("title", ""),
                    description=request.POST.get("description", ""),
                    kind=request.POST.get("kind", ResourceKind.TEXT),
                    occurrence=occurrence,
                    text_content=request.POST.get("text_content", ""),
                    external_url=request.POST.get("external_url", ""),
                    uploaded_file=request.FILES.get("file"),
                    visibility=request.POST.get("visibility", ResourceVisibility.PARTICIPANT),
                    significant_update=request.POST.get("significant_update") == "on",
                )
                messages.success(request, f"Resource « {resource.title} » créée en brouillon.")
            elif action == "publish":
                resource = get_object_or_404(ActivityResource, pk=request.POST.get("resource_id"), activity=activity)
                publish_resource(resource=resource, actor=request.user)
                messages.success(request, "Resource publiée.")
            elif action == "replace":
                resource = get_object_or_404(ActivityResource, pk=request.POST.get("resource_id"), activity=activity)
                replace_resource(
                    resource=resource,
                    actor=request.user,
                    title=request.POST.get("title") or resource.title,
                    description=request.POST.get("description", resource.description),
                    kind=request.POST.get("kind") or resource.kind,
                    text_content=request.POST.get("text_content", ""),
                    external_url=request.POST.get("external_url", ""),
                    uploaded_file=request.FILES.get("file"),
                    visibility=request.POST.get("visibility") or resource.visibility,
                    significant_update=request.POST.get("significant_update") == "on",
                )
                messages.success(request, "Nouvelle version publiée et provenance préservée.")
            else:
                raise ValidationError("Action Resource inconnue.")
        except (ValidationError, PermissionDenied, ValueError) as exc:
            messages.error(request, "; ".join(getattr(exc, "messages", [str(exc)])))
        return redirect("preparation:manage", activity_id=activity.pk)
