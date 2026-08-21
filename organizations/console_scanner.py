from django.core.exceptions import PermissionDenied, ValidationError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views import View
from django.views.generic import TemplateView

from access.models import AccessUseResult
from access.services import resolve_access_credential, validate_access
from activities.models import Activity
from authorization.constants import PermissionCode
from authorization.services import can
from core.product_language import access_status_label, vocabulary_for
from scanner.models import ScannerAssignment

from .console_views import SpaceConsoleMixin


def _scanner_message(outcome, activity):
    vocabulary = vocabulary_for(activity=activity)
    if outcome.result == AccessUseResult.ACCEPTED:
        if vocabulary.vertical == "transport":
            return "Voyageur autorisé à embarquer."
        if vocabulary.vertical == "event":
            return "Entrée autorisée."
        return "Accès autorisé."
    if outcome.result == AccessUseResult.ALREADY_USED:
        return "Ce billet a déjà été utilisé."
    if outcome.result == AccessUseResult.NOT_YET_VALID:
        return "Ce billet n’est pas encore valable."
    if outcome.result == AccessUseResult.EXPIRED:
        return "Ce billet est expiré."
    if outcome.result == AccessUseResult.REVOKED:
        return "Ce billet a été révoqué."
    if outcome.result == AccessUseResult.CANCELLED:
        return "Ce billet a été annulé."
    if outcome.result == AccessUseResult.WRONG_OCCURRENCE:
        return "Mauvais départ." if vocabulary.vertical == "transport" else "Cet accès n’est pas valable pour cette date."
    if outcome.result == AccessUseResult.WRONG_ACTIVITY:
        return "Ce billet n’est pas valable pour cette activité."
    if outcome.result == AccessUseResult.INVALID_CREDENTIAL:
        return "QR non valide."
    return "Contrôle refusé."


class _SpaceActivityScannerMixin(SpaceConsoleMixin):
    module_key = "control"

    def get_activity(self):
        queryset = Activity.objects.filter(space=self.space)
        if self.space_console.activity_ids is not None:
            queryset = queryset.filter(pk__in=self.space_console.activity_ids)
        activity = get_object_or_404(queryset, pk=self.kwargs["activity_id"])
        if not can(self.request.user, PermissionCode.ACTIVITY_ACCESS_SCAN, activity=activity):
            raise PermissionDenied("Vous n’avez pas l’autorisation de contrôler les accès de cette activité.")
        return activity

    def get_occurrence(self, activity):
        occurrence_id = (self.request.POST.get("occurrence") or "").strip()
        if occurrence_id:
            return get_object_or_404(activity.occurrences.all(), pk=occurrence_id)
        assignment = (
            ScannerAssignment.objects.filter(
                agent=self.request.user,
                activity=activity,
                occurrence__isnull=False,
                is_active=True,
            )
            .select_related("occurrence")
            .order_by("created_at", "id")
            .first()
        )
        return assignment.occurrence if assignment else None

    def validate_token(self, *, activity, occurrence, token):
        credential = resolve_access_credential(token)
        return validate_access(
            access=credential.access,
            credential=credential,
            controller=self.request.user,
            authority_check=lambda actor, access: can(
                actor,
                PermissionCode.ACTIVITY_ACCESS_SCAN,
                activity=access.activity,
            ),
            expected_activity=activity,
            expected_occurrence=occurrence,
            source="space_console",
        )


class SpaceActivityScannerView(_SpaceActivityScannerMixin, TemplateView):
    template_name = "organizations/console/scanner.html"
    page_title = "Scanner"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        activity = self.get_activity()
        context["activity"] = activity
        context["console_page_title"] = f"Contrôle · {activity.title}"
        context["occurrences"] = activity.occurrences.order_by("start_at", "id")
        context["scanner_assignment"] = (
            ScannerAssignment.objects.filter(
                agent=self.request.user,
                activity=activity,
                occurrence__isnull=False,
                is_active=True,
            )
            .select_related("occurrence")
            .order_by("created_at", "id")
            .first()
        )
        return context


class SpaceActivityScannerAPIView(_SpaceActivityScannerMixin, View):
    def post(self, request, *args, **kwargs):
        activity = self.get_activity()
        occurrence = self.get_occurrence(activity)
        token = (request.POST.get("token") or "").strip()
        try:
            outcome = self.validate_token(activity=activity, occurrence=occurrence, token=token)
        except ValidationError:
            return JsonResponse({"accepted": False, "message": "QR non valide."}, status=400)
        return JsonResponse(
            {
                "accepted": outcome.accepted,
                "result": outcome.result,
                "message": _scanner_message(outcome, activity),
                "access": {
                    "beneficiary": outcome.access.beneficiary.full_name or outcome.access.beneficiary.email,
                    "status": access_status_label(outcome.access.status),
                }
                if outcome.access
                else None,
            }
        )
