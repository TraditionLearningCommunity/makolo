from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import redirect
from django.views.generic import FormView

from activities.models import ActivityStatus
from authorization.constants import PermissionCode
from authorization.services import activity_ids_with_permission

from access.manual_grants import grant_access_manually

from .console_selectors import activities_manageable_for_access
from .console_views import SpaceConsoleAccessView as BaseSpaceConsoleAccessView
from .console_views import SpaceConsoleMixin
from .forms import ManualAccessGrantForm


_TERMINAL_ACTIVITY_STATUSES = {
    ActivityStatus.CANCELLED,
    ActivityStatus.COMPLETED,
    ActivityStatus.ARCHIVED,
}


def _grantable_activities(context):
    return activities_manageable_for_access(context).exclude(
        status__in=_TERMINAL_ACTIVITY_STATUSES
    )


class SpaceConsoleAccessView(BaseSpaceConsoleAccessView):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["can_grant_access"] = _grantable_activities(self.space_console).exists()

        allowed_ids = activity_ids_with_permission(
            self.request.user,
            PermissionCode.ACTIVITY_ACCESS_MANAGE,
        )
        page_obj = context.get("page_obj")
        if page_obj is not None:
            for access in page_obj.object_list:
                access.console_can_manage = (
                    allowed_ids is None or access.activity_id in allowed_ids
                )
        return context


class SpaceConsoleGrantAccessView(SpaceConsoleMixin, FormView):
    template_name = "organizations/console/access_grant.html"
    form_class = ManualAccessGrantForm
    module_key = "access"
    page_title = "Accorder un accès"

    def _ensure_manageable_activity(self):
        if not _grantable_activities(self.space_console).exists():
            raise PermissionDenied(
                "Vous ne pouvez accorder d’accès à aucune activité de cet Espace."
            )

    def get(self, request, *args, **kwargs):
        self._ensure_manageable_activity()
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self._ensure_manageable_activity()
        return super().post(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update({"actor": self.request.user, "space": self.space})
        return kwargs

    def form_valid(self, form):
        try:
            access = grant_access_manually(
                actor=self.request.user,
                beneficiary=form.cleaned_data["beneficiary"],
                activity=form.cleaned_data["activity"],
                occurrence=form.cleaned_data.get("occurrence"),
                reason=form.cleaned_data.get("reason", ""),
            )
        except PermissionDenied:
            raise
        except ValidationError as exc:
            form.add_error(None, "; ".join(getattr(exc, "messages", [str(exc)])))
            return self.form_invalid(form)

        beneficiary_name = access.beneficiary.get_full_name().strip() or access.beneficiary.username
        messages.success(
            self.request,
            f"Accès accordé à {beneficiary_name} pour {access.activity.title}.",
        )
        return redirect("organizations:console-access", slug=self.space.slug)
